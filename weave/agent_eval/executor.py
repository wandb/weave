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
    job_result: JobResult
    scores: dict[str, ScoreResult] = field(default_factory=dict)
    error: str | None = None

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
    ):
        self.config = config
        self.config_dir = config_dir or Path.cwd()
        self.driver: Driver | None = None
        self.artifacts: ArtifactManager | None = None
        self._log = log or _default_log

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

            # Execute each combination
            for i, (harness_config, task_config) in enumerate(combinations, 1):
                self.log(f"[{i}/{len(combinations)}] Running task: {task_config.id}")
                self.log(f"  Harness: {harness_config.type.value}:{harness_config.model}")
                
                task_result = await self._run_task(
                    run, harness_config, task_config, env
                )
                result.task_results.append(task_result)
                
                # Show result
                if task_result.success:
                    status = "PASS" if task_result.overall_pass else "FAIL"
                    self.log(f"  Result: {status}")
                    if task_result.scores:
                        for name, score in task_result.scores.items():
                            self.log(f"    {name}: {score.score:.0f}%")
                else:
                    self.log(f"  Result: ERROR - {task_result.error}")
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

        return result

    def _resolve_env(self) -> dict[str, str]:
        """Resolve required environment variables."""
        required_keys: set[str] = set()

        # Collect from all harnesses in matrix
        if self.config.matrix:
            for harness_config in self.config.matrix.harness:
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
                job_result=JobResult(
                    exit_code=-1,
                    artifacts_path=task_artifacts.path,
                    duration_seconds=0,
                    error=f"Image build failed: {image_result.error}",
                ),
                error=image_result.error,
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
        )
        self.log(f"  Harness completed in {job_result.duration_seconds:.1f}s (exit code: {job_result.exit_code})")

        # Update metadata
        task_artifacts.write_metadata({
            **task_artifacts.read_metadata(),
            "completed_at": datetime.now().isoformat(),
            "exit_code": job_result.exit_code,
            "duration_seconds": job_result.duration_seconds,
        })

        task_result = TaskResult(
            task_id=task_config.id,
            harness=harness_config.type.value,
            model=harness_config.model,
            job_result=job_result,
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
            # TODO: Implement LLM rubric scorer
            pass

        # Custom scorers
        for custom_config in self.config.scoring.custom:
            # TODO: Implement custom scorer support
            pass

        return scores
