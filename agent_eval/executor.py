"""Job orchestration for evaluation runs."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .artifacts import ArtifactManager, RunArtifacts, TaskArtifacts
from .config.schema import EvalConfig, HarnessConfig, TaskConfig
from .drivers.base import Driver, JobResult, create_driver
from .harnesses.base import HarnessAdapter
from .harnesses.registry import get_harness
from .scorers.base import ScoreResult, Scorer
from .scorers.deterministic import DeterministicScorer
from .scorers.llm_rubric import LLMRubricScorer


def _default_log(msg: str, end: str = "\n") -> None:
    """Default logging function that writes to stderr."""
    sys.stderr.write(msg + end)
    sys.stderr.flush()


@dataclass
class TaskResult:
    """Result of a single task execution."""

    task_id: str
    harness: str
    model: str
    prompt: str  # The task prompt (input to the agent)
    job_result: JobResult
    scores: dict[str, ScoreResult] = field(default_factory=dict)
    error: str | None = None
    timeout: int = 60  # Task timeout in seconds

    @property
    def success(self) -> bool:
        return self.job_result.success and self.error is None

    @property
    def overall_pass(self) -> bool:
        if not self.success:
            return False
        return all(s.overall_pass for s in self.scores.values())


@dataclass
class EvalResult:
    """Result of a full evaluation run."""

    run_id: str
    config_name: str
    started_at: datetime
    completed_at: datetime | None = None
    task_results: list[TaskResult] = field(default_factory=list)
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None and all(r.success for r in self.task_results)

    @property
    def pass_rate(self) -> float:
        if not self.task_results:
            return 0.0
        passed = sum(1 for r in self.task_results if r.overall_pass)
        return passed / len(self.task_results) * 100

    def summary(self) -> dict[str, Any]:
        """Generate summary statistics."""
        return {
            "run_id": self.run_id,
            "config_name": self.config_name,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_tasks": len(self.task_results),
            "passed_tasks": sum(1 for r in self.task_results if r.overall_pass),
            "failed_tasks": sum(1 for r in self.task_results if not r.overall_pass),
            "pass_rate": self.pass_rate,
            "success": self.success,
            "error": self.error,
        }


class Executor:
    """Orchestrates evaluation runs."""

    def __init__(
        self,
        config: EvalConfig,
        config_dir: Path | None = None,
        log: Callable[[str], None] | None = None,
        max_parallel: int = 8,
        weave_project: str | None = None,
    ):
        self.config = config
        self.config_dir = config_dir or Path.cwd()
        self.driver: Driver | None = None
        self.artifacts: ArtifactManager | None = None
        self._log = log or _default_log
        self.max_parallel = max_parallel
        self._log_lock = asyncio.Lock()
        self.weave_project = weave_project

    async def log_async(self, msg: str, end: str = "\n") -> None:
        """Log a message to the output (thread-safe for parallel execution)."""
        async with self._log_lock:
            self._log(msg, end)

    def log(self, msg: str, end: str = "\n") -> None:
        """Log a message to the output."""
        self._log(msg, end)

    async def run(self) -> EvalResult:
        """Execute the full evaluation.

        Returns:
            EvalResult with all task results.
        """
        started_at = datetime.now()

        self.log(f"Starting evaluation run...")

        # Initialize artifacts manager
        output_dir = self.config_dir / self.config.output.directory
        self.artifacts = ArtifactManager(output_dir)
        run = self.artifacts.create_run()

        self.log(f"Run ID: {run.run_id}")
        self.log(f"Output directory: {output_dir}")

        result = EvalResult(
            run_id=run.run_id,
            config_name=self.config.name,
            started_at=started_at,
        )

        # Initialize Weave logger if configured (outside try block for final summary)
        weave_logger = None
        if self.weave_project:
            from .reporter import WeaveConfig, WeaveLogger
            weave_config = WeaveConfig(project=self.weave_project)
            weave_logger = WeaveLogger(
                config_name=self.config.name,
                weave_config=weave_config,
                artifacts_base_path=output_dir,
            )

        try:
            # Resolve environment variables
            self.log("Resolving environment variables...")
            env = self._resolve_env()
            self.log(f"  Found {len(env)} required variables")

            # Create driver
            self.log(f"Initializing {self.config.driver.type.value} driver...")
            self.driver = create_driver(self.config.driver)

            # Expand matrix
            combinations = self.config.expand_matrix()
            self.log(f"Expanded matrix: {len(combinations)} task/harness combinations")

            # Write run metadata
            run.write_metadata({
                "config_name": self.config.name,
                "started_at": started_at.isoformat(),
                "total_combinations": len(combinations),
                "environment": {
                    "base_image": self.config.environment.base_image,
                    "git": self.config.environment.git.model_dump() if self.config.environment.git else None,
                },
            })

            self.log("")

            # Group combinations by model for streaming Weave results
            combinations_by_model: dict[str, list[tuple[int, HarnessConfig, TaskConfig]]] = {}
            for i, (harness_config, task_config) in enumerate(combinations, 1):
                model_key = f"{harness_config.type.value}:{harness_config.model}"
                if model_key not in combinations_by_model:
                    combinations_by_model[model_key] = []
                combinations_by_model[model_key].append((i, harness_config, task_config))

            # Execute combinations in parallel with concurrency limit
            if self.max_parallel > 1 and len(combinations) > 1:
                self.log(f"Running {len(combinations)} tasks in parallel (max {self.max_parallel} concurrent)...")
                self.log("")
                
                # Create semaphore to limit concurrency
                semaphore = asyncio.Semaphore(self.max_parallel)
                
                # Track results per model for streaming Weave logs
                results_by_model: dict[str, list[TaskResult]] = {k: [] for k in combinations_by_model}
                pending_per_model: dict[str, int] = {k: len(v) for k, v in combinations_by_model.items()}
                results_lock = asyncio.Lock()
                
                async def run_with_semaphore(idx: int, harness_config: HarnessConfig, task_config: TaskConfig) -> TaskResult:
                    async with semaphore:
                        model_key = f"{harness_config.type.value}:{harness_config.model}"
                        await self.log_async(f"[{idx}/{len(combinations)}] Starting: {task_config.id} ({model_key})")
                        
                        task_result = await self._run_task(
                            run, harness_config, task_config, env
                        )
                        
                        # Log completion
                        if task_result.success:
                            status = "PASS" if task_result.overall_pass else "FAIL"
                            score_info = ""
                            if task_result.scores:
                                scores_str = ", ".join(f"{n}: {s.score:.0f}%" for n, s in task_result.scores.items())
                                score_info = f" [{scores_str}]"
                            await self.log_async(f"[{idx}/{len(combinations)}] Completed: {task_config.id} ({model_key}) -> {status}{score_info}")
                        else:
                            await self.log_async(f"[{idx}/{len(combinations)}] Completed: {task_config.id} ({model_key}) -> ERROR: {task_result.error}")
                        
                        # Track result and stream to Weave when model is complete
                        async with results_lock:
                            results_by_model[model_key].append(task_result)
                            pending_per_model[model_key] -= 1
                            
                            # If all tasks for this model are done, log to Weave immediately
                            if pending_per_model[model_key] == 0 and weave_logger:
                                try:
                                    url = weave_logger.log_model_results(
                                        harness_type=harness_config.type.value,
                                        model=harness_config.model,
                                        task_results=results_by_model[model_key],
                                    )
                                    await self.log_async(f"  -> Logged {model_key} to Weave: {url}")
                                except Exception as e:
                                    await self.log_async(f"  -> Error logging {model_key} to Weave: {e}")
                        
                        return task_result
                
                # Launch all tasks
                tasks = [
                    run_with_semaphore(i, harness_config, task_config)
                    for i, harness_config, task_config in [
                        item for items in combinations_by_model.values() for item in items
                    ]
                ]
                
                # Wait for all to complete
                task_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for i, task_result in enumerate(task_results):
                    if isinstance(task_result, Exception):
                        # Handle exceptions from individual tasks
                        flat_combinations = [item for items in combinations_by_model.values() for item in items]
                        _, harness_config, task_config = flat_combinations[i]
                        result.task_results.append(TaskResult(
                            task_id=task_config.id,
                            harness=harness_config.type.value,
                            model=harness_config.model,
                            prompt=task_config.prompt,
                            job_result=JobResult(
                                exit_code=-1,
                                artifacts_path=Path("."),
                                duration_seconds=0,
                                error=str(task_result),
                            ),
                            error=str(task_result),
                            timeout=task_config.timeout,
                        ))
                    else:
                        result.task_results.append(task_result)
            else:
                # Sequential execution
                results_by_model: dict[str, list[TaskResult]] = {}
                
                for i, (harness_config, task_config) in enumerate(combinations, 1):
                    model_key = f"{harness_config.type.value}:{harness_config.model}"
                    self.log(f"[{i}/{len(combinations)}] Running task: {task_config.id}")
                    self.log(f"  Harness: {model_key}")
                    
                    task_result = await self._run_task(
                        run, harness_config, task_config, env
                    )
                    result.task_results.append(task_result)
                    
                    # Track for Weave
                    if model_key not in results_by_model:
                        results_by_model[model_key] = []
                    results_by_model[model_key].append(task_result)
                    
                    # Show result
                    if task_result.success:
                        status = "PASS" if task_result.overall_pass else "FAIL"
                        self.log(f"  Result: {status}")
                        if task_result.scores:
                            for name, score in task_result.scores.items():
                                self.log(f"    {name}: {score.score:.0f}%")
                    else:
                        self.log(f"  Result: ERROR - {task_result.error}")
                    
                    # Check if this model is now complete and log to Weave
                    expected_tasks = len([c for c in combinations if f"{c[0].type.value}:{c[0].model}" == model_key])
                    if len(results_by_model[model_key]) == expected_tasks and weave_logger:
                        try:
                            url = weave_logger.log_model_results(
                                harness_type=harness_config.type.value,
                                model=harness_config.model,
                                task_results=results_by_model[model_key],
                            )
                            self.log(f"  -> Logged {model_key} to Weave: {url}")
                        except Exception as e:
                            self.log(f"  -> Error logging {model_key} to Weave: {e}")
                    
                    self.log("")

        except Exception as e:
            self.log(f"Error: {e}")
            result.error = str(e)

        result.completed_at = datetime.now()
        duration = (result.completed_at - started_at).total_seconds()

        # Update run metadata
        run.write_metadata({
            **run.read_metadata(),
            "completed_at": result.completed_at.isoformat(),
            "summary": result.summary(),
        })

        self.log(f"Evaluation completed in {duration:.1f}s")
        
        # Show Weave summary if we logged anything
        if weave_logger and weave_logger.eval_urls:
            self.log(f"Weave: {len(weave_logger.eval_urls)} models logged")

        return result

    def _resolve_env(self) -> dict[str, str]:
        """Resolve required environment variables."""
        required_keys: set[str] = set()

        # Get harnesses from expanded matrix (handles default harness case)
        combinations = self.config.expand_matrix()
        seen_harnesses: set[tuple[str, str]] = set()
        
        for harness_config, _ in combinations:
            # Avoid duplicate checks for same harness
            key = (harness_config.type.value, harness_config.model)
            if key in seen_harnesses:
                continue
            seen_harnesses.add(key)
            
            adapter = get_harness(harness_config)
            required_keys.update(adapter.required_env_keys(harness_config))

        # Add environment-specified keys
        required_keys.update(self.config.environment.additional_env_keys)

        # Add scorer keys
        # TODO: Add when LLM rubric scorer is implemented

        # Resolve from environment
        env: dict[str, str] = {}
        missing: list[str] = []

        for key in required_keys:
            value = os.environ.get(key)
            if value:
                env[key] = value
            else:
                missing.append(key)

        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(sorted(missing))}"
            )

        return env

    async def _run_task(
        self,
        run: RunArtifacts,
        harness_config: HarnessConfig,
        task_config: TaskConfig,
        env: dict[str, str],
    ) -> TaskResult:
        """Run a single task."""
        harness_id = f"{harness_config.type.value}_{harness_config.model}"
        harness_id = harness_id.replace("/", "_").replace(":", "_")

        task_artifacts = run.create_task(task_config.id, harness_id)
        task_artifacts.setup()

        # Get harness adapter
        adapter = get_harness(harness_config)

        # Build image
        self.log(f"  Building container image...")
        skill_path = self.config_dir / self.config.skill.path
        layers = [self.config_dir / layer for layer in self.config.environment.layers]

        build_start = time.time()
        image_result = await self.driver.build_image(
            base_image=self.config.environment.base_image,
            layers=layers,
            skill_path=skill_path,
            adapter_script=adapter.get_adapter_script_path(),
            setup_commands=self.config.environment.setup + adapter.get_setup_commands(),
            tag=f"agent-eval-{self.config.name}-{task_config.id}",
        )
        build_duration = time.time() - build_start

        if not image_result.success:
            self.log(f"  Image build failed after {build_duration:.1f}s")
            return TaskResult(
                task_id=task_config.id,
                harness=harness_config.type.value,
                model=harness_config.model,
                prompt=task_config.prompt,
                job_result=JobResult(
                    exit_code=-1,
                    artifacts_path=task_artifacts.path,
                    duration_seconds=0,
                    error=f"Image build failed: {image_result.error}",
                ),
                error=image_result.error,
                timeout=task_config.timeout,
            )
        
        self.log(f"  Image built in {build_duration:.1f}s")

        # Build command
        command = adapter.build_command(
            prompt=task_config.prompt,
            skill_path="/skill",
            workdir="/workspace",
            timeout=task_config.timeout,
            model=harness_config.model,
            extra_args=harness_config.args,
        )

        # Merge environment
        harness_env = adapter.build_env(
            prompt=task_config.prompt,
            skill_path="/skill",
            workdir="/workspace",
            timeout=task_config.timeout,
            model=harness_config.model,
        )
        full_env = {**env, **harness_env}

        # Write task metadata
        task_artifacts.write_metadata({
            "task_id": task_config.id,
            "harness": harness_config.type.value,
            "model": harness_config.model,
            "prompt": task_config.prompt,
            "timeout": task_config.timeout,
            "expected_trigger": task_config.expected_trigger,
            "started_at": datetime.now().isoformat(),
        })

        # Run job
        self.log(f"  Running harness (timeout: {task_config.timeout}s)...")
        job_result = await self.driver.run_job(
            image=image_result.image_id,
            command=command,
            env=full_env,
            timeout=task_config.timeout,
            artifacts_dir=task_artifacts.path,
            network_allowlist=self.config.network.allowed_hosts,
            use_host_network=self.config.driver.use_host_network,
        )
        self.log(f"  Harness completed in {job_result.duration_seconds:.1f}s (exit code: {job_result.exit_code})")

        # Extract and save metrics
        from .metrics import extract_metrics
        metrics = extract_metrics(task_artifacts.path)
        
        # Update metadata with metrics
        task_artifacts.write_metadata({
            **task_artifacts.read_metadata(),
            "completed_at": datetime.now().isoformat(),
            "exit_code": job_result.exit_code,
            "duration_seconds": job_result.duration_seconds,
            "metrics": metrics.to_dict(),
        })
        
        # Log key metrics
        if metrics.total_tokens > 0:
            self.log(f"  Tokens: {metrics.total_tokens} (in: {metrics.input_tokens}, out: {metrics.output_tokens})")
        if metrics.command_count > 0:
            self.log(f"  Commands executed: {metrics.command_count}")

        task_result = TaskResult(
            task_id=task_config.id,
            harness=harness_config.type.value,
            model=harness_config.model,
            prompt=task_config.prompt,
            job_result=job_result,
            timeout=task_config.timeout,
            error=job_result.error,  # Propagate job error to task result
        )

        # Run scorers if job succeeded
        if job_result.success:
            self.log(f"  Running scorers...")
            scores = await self._run_scorers(task_artifacts)
            task_result.scores = scores

            # Write scores to artifacts
            for scorer_name, score in scores.items():
                task_artifacts.write_score(scorer_name, score.to_dict())
        elif job_result.error:
            self.log(f"  Skipping scoring due to job error: {job_result.error}")

        # Cleanup image
        self.log(f"  Cleaning up...")
        try:
            await self.driver.cleanup(image_result.image_id)
        except Exception:
            pass  # Ignore cleanup errors

        return task_result

    async def _run_scorers(self, task_artifacts: TaskArtifacts) -> dict[str, ScoreResult]:
        """Run all configured scorers."""
        scores: dict[str, ScoreResult] = {}

        # Deterministic scorer
        if self.config.scoring.deterministic:
            scorer = DeterministicScorer(self.config.scoring.deterministic)
            scores[scorer.name] = await scorer.score(task_artifacts.path)

        # LLM rubric scorer
        if self.config.scoring.rubric:
            scorer = LLMRubricScorer(self.config.scoring.rubric)
            scores[scorer.name] = await scorer.score(task_artifacts.path)

        # Custom scorers
        for custom_config in self.config.scoring.custom:
            # TODO: Implement custom scorer support
            pass

        return scores
