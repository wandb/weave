"""LLM-based rubric scorer for qualitative evaluation.

This scorer runs in a Docker container to evaluate workspace contents
against a rubric using an LLM.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .base import CheckResult, ScoreResult, Scorer

if TYPE_CHECKING:
    from ..config.schema import LLMRubricConfig


# Python script that runs inside the container to do the LLM evaluation
SCORER_SCRIPT = '''
#!/usr/bin/env python3
"""LLM Rubric Scorer - runs inside container."""

import fnmatch
import json
import os
import sys
from pathlib import Path


def parse_gitignore(workspace_path: Path) -> list[str]:
    """Parse .gitignore file and return list of patterns."""
    gitignore_path = workspace_path / ".gitignore"
    patterns = []
    
    # Always ignore these directories regardless of .gitignore
    default_ignores = [
        ".git",
        ".git/**",
        "node_modules",
        "node_modules/**",
        "__pycache__",
        "__pycache__/**",
        "*.pyc",
        ".npm",
        ".npm/**",
        ".cache",
        ".cache/**",
    ]
    patterns.extend(default_ignores)
    
    if gitignore_path.exists():
        try:
            for line in gitignore_path.read_text().splitlines():
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue
                patterns.append(line)
        except Exception:
            pass
    
    return patterns


def is_ignored(path: Path, workspace_path: Path, patterns: list[str]) -> bool:
    """Check if a path matches any gitignore pattern."""
    try:
        rel_path = path.relative_to(workspace_path)
        rel_str = str(rel_path)
        
        for pattern in patterns:
            # Handle directory patterns (ending with /)
            if pattern.endswith("/"):
                pattern = pattern[:-1]
                if fnmatch.fnmatch(rel_str, pattern) or fnmatch.fnmatch(rel_str, pattern + "/**"):
                    return True
                # Check if any parent matches
                for parent in rel_path.parents:
                    if fnmatch.fnmatch(str(parent), pattern):
                        return True
            else:
                # Regular pattern
                if fnmatch.fnmatch(rel_str, pattern):
                    return True
                # Also check just the filename
                if fnmatch.fnmatch(path.name, pattern):
                    return True
                # Check with ** prefix for nested matches
                if fnmatch.fnmatch(rel_str, "**/" + pattern):
                    return True
        
        return False
    except ValueError:
        return True  # Path not relative to workspace, ignore it


def is_binary(file_path: Path) -> bool:
    """Check if a file is binary by reading first few bytes."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(8192)
            # Check for null bytes (common in binary files)
            if b"\\x00" in chunk:
                return True
            # Try to decode as UTF-8
            try:
                chunk.decode("utf-8")
                return False
            except UnicodeDecodeError:
                return True
    except Exception:
        return True


def collect_workspace_context(workspace_path: Path) -> str:
    """Collect relevant files from workspace for LLM context.
    
    Respects .gitignore patterns and skips binary files.
    """
    context_parts = []
    
    # Parse gitignore patterns
    patterns = parse_gitignore(workspace_path)
    
    files_found = []
    if workspace_path.exists():
        for file_path in workspace_path.rglob("*"):
            if not file_path.is_file():
                continue
            if is_ignored(file_path, workspace_path, patterns):
                continue
            if is_binary(file_path):
                continue
            files_found.append(file_path)
    
    files_found.sort(key=lambda p: str(p))
    
    max_file_size = 10000
    max_total_size = 100000
    total_size = 0
    
    for file_path in files_found:
        if total_size >= max_total_size:
            context_parts.append(f"\\n... (truncated, more files exist)")
            break
            
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            if len(content) > max_file_size:
                content = content[:max_file_size] + "\\n... (truncated)"
            
            rel_path = file_path.relative_to(workspace_path)
            context_parts.append(f"### {rel_path}\\n```\\n{content}\\n```\\n")
            total_size += len(content)
        except Exception as e:
            rel_path = file_path.relative_to(workspace_path)
            context_parts.append(f"### {rel_path}\\n(Error reading file: {e})\\n")
    
    if not context_parts:
        return "(No relevant files found in workspace)"
    
    return "\\n".join(context_parts)


def run_openai_eval(rubric_prompt: str, workspace_context: str, model: str) -> dict:
    """Run evaluation using OpenAI API."""
    from openai import OpenAI
    
    client = OpenAI()
    
    system_prompt = """You are an expert code evaluator. Your task is to evaluate code against a rubric and return a structured assessment.

You will be given:
1. A rubric describing what to evaluate
2. The contents of a workspace with code files

Evaluate the code against each criterion in the rubric. Be objective and thorough.

Return your evaluation as JSON with this structure:
{
  "overall_pass": boolean,
  "score": integer (0-100),
  "checks": [
    {
      "id": "check_id",
      "pass": boolean,
      "notes": "string"
    }
  ]
}

Be strict but fair. If something is partially implemented, explain what's missing."""

    user_prompt = f"""## Rubric

{rubric_prompt}

## Workspace Contents

{workspace_context}

## Instructions

Evaluate the workspace against the rubric above. Return your assessment as JSON."""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    
    result = json.loads(response.choices[0].message.content)
    result["_usage"] = {
        "input_tokens": response.usage.prompt_tokens if response.usage else 0,
        "output_tokens": response.usage.completion_tokens if response.usage else 0,
        "total_tokens": response.usage.total_tokens if response.usage else 0,
    }
    return result


def run_anthropic_eval(rubric_prompt: str, workspace_context: str, model: str) -> dict:
    """Run evaluation using Anthropic API."""
    import anthropic
    
    client = anthropic.Anthropic()
    
    system_prompt = """You are an expert code evaluator. Your task is to evaluate code against a rubric and return a structured assessment.

You will be given:
1. A rubric describing what to evaluate
2. The contents of a workspace with code files

Evaluate the code against each criterion in the rubric. Be objective and thorough.

Return your evaluation as JSON with this structure:
{
  "overall_pass": boolean,
  "score": integer (0-100),
  "checks": [
    {
      "id": "check_id",
      "pass": boolean,
      "notes": "string"
    }
  ]
}

Be strict but fair. If something is partially implemented, explain what's missing."""

    user_prompt = f"""## Rubric

{rubric_prompt}

## Workspace Contents

{workspace_context}

## Instructions

Evaluate the workspace against the rubric above. Return your assessment as JSON."""

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt},
        ],
    )
    
    # Extract JSON from response
    content = response.content[0].text
    result = json.loads(content)
    result["_usage"] = {
        "input_tokens": response.usage.input_tokens if response.usage else 0,
        "output_tokens": response.usage.output_tokens if response.usage else 0,
        "total_tokens": (response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0,
    }
    return result


def main():
    # Read config from environment
    rubric_prompt = os.environ.get("RUBRIC_PROMPT", "")
    model = os.environ.get("RUBRIC_MODEL", "gpt-4o")
    workspace_path = Path(os.environ.get("WORKSPACE_PATH", "/workspace"))
    output_path = Path(os.environ.get("OUTPUT_PATH", "/output/score.json"))
    
    if not rubric_prompt:
        print("Error: RUBRIC_PROMPT environment variable required", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Collect workspace context
        workspace_context = collect_workspace_context(workspace_path)
        
        # Determine which API to use based on model
        if "claude" in model.lower() or "anthropic" in model.lower():
            result = run_anthropic_eval(rubric_prompt, workspace_context, model)
        else:
            result = run_openai_eval(rubric_prompt, workspace_context, model)
        
        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2))
        
        # Also print to stdout for logging
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        error_result = {
            "overall_pass": False,
            "score": 0,
            "checks": [{"id": "error", "pass": False, "notes": str(e)}],
            "error": str(e),
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(error_result, indent=2))
        print(json.dumps(error_result, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
'''


class LLMRubricScorer(Scorer):
    """Scorer that uses an LLM to evaluate against a rubric.
    
    This scorer runs in a Docker container with the necessary dependencies
    to call OpenAI or Anthropic APIs.
    """

    def __init__(self, config: LLMRubricConfig):
        self.config = config

    @property
    def name(self) -> str:
        return "rubric"

    def required_env_keys(self) -> list[str]:
        """LLM rubric requires an API key based on the model."""
        model = self.config.model.lower()
        if "claude" in model or "anthropic" in model:
            return ["ANTHROPIC_API_KEY"]
        return ["OPENAI_API_KEY"]

    async def score(self, artifacts_path: Path) -> ScoreResult:
        """Score artifacts by running LLM evaluation in a container."""
        import os
        
        start_time = time.time()
        
        workspace_path = artifacts_path / "workspace"
        scores_dir = artifacts_path / "scores"
        scores_dir.mkdir(parents=True, exist_ok=True)
        
        # Create temporary directory for scorer script
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Write scorer script
            script_path = tmpdir_path / "scorer.py"
            script_path.write_text(SCORER_SCRIPT)
            
            # Build environment variables
            env_vars = {
                "RUBRIC_PROMPT": self.config.prompt,
                "RUBRIC_MODEL": self.config.model,
                "WORKSPACE_PATH": "/workspace",
                "OUTPUT_PATH": "/output/score.json",
            }
            
            # Add API keys from host environment
            for key in self.required_env_keys():
                value = os.environ.get(key)
                if value:
                    env_vars[key] = value
            
            # Build docker command
            docker_cmd = [
                "docker", "run", "--rm",
                "--network=host",  # For API access
            ]
            
            # Add environment variables
            for key, value in env_vars.items():
                docker_cmd.extend(["-e", f"{key}={value}"])
            
            # Mount workspace (read-only)
            docker_cmd.extend(["-v", f"{workspace_path.absolute()}:/workspace:ro"])
            
            # Mount output directory
            docker_cmd.extend(["-v", f"{scores_dir.absolute()}:/output"])
            
            # Mount scorer script
            docker_cmd.extend(["-v", f"{script_path.absolute()}:/scorer.py:ro"])
            
            # Use Python image with dependencies
            docker_cmd.extend([
                "python:3.12-slim",
                "sh", "-c",
                "pip install -q openai anthropic && python /scorer.py"
            ])
            
            # Run the container
            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=120  # 2 minute timeout for scorer
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ScoreResult(
                    overall_pass=False,
                    score=0,
                    checks=[CheckResult(id="timeout", passed=False, notes="Scorer timed out after 120s")],
                    metadata={"scorer": self.name, "error": "timeout"},
                )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Read results from output file
        output_file = scores_dir / "score.json"
        if output_file.exists():
            try:
                result_data = json.loads(output_file.read_text())
                
                # Extract usage info
                usage = result_data.pop("_usage", {})
                error = result_data.pop("error", None)
                
                checks = [
                    CheckResult(
                        id=c.get("id", "unknown"),
                        passed=c.get("pass", False),
                        notes=c.get("notes", ""),
                    )
                    for c in result_data.get("checks", [])
                ]
                
                return ScoreResult(
                    overall_pass=result_data.get("overall_pass", False),
                    score=result_data.get("score", 0),
                    checks=checks,
                    metadata={
                        "scorer": self.name,
                        "version": "1.0",
                        "duration_ms": duration_ms,
                        "model": self.config.model,
                        "usage": usage,
                        "checks_passed": sum(1 for c in checks if c.passed),
                        "checks_total": len(checks),
                        **({"error": error} if error else {}),
                    },
                )
            except Exception as e:
                return ScoreResult(
                    overall_pass=False,
                    score=0,
                    checks=[CheckResult(id="parse_error", passed=False, notes=f"Failed to parse scorer output: {e}")],
                    metadata={"scorer": self.name, "duration_ms": duration_ms, "error": str(e)},
                )
        else:
            # No output file - check stderr for errors
            stderr_text = stderr.decode() if stderr else ""
            return ScoreResult(
                overall_pass=False,
                score=0,
                checks=[CheckResult(id="no_output", passed=False, notes=f"Scorer produced no output. stderr: {stderr_text[:500]}")],
                metadata={"scorer": self.name, "duration_ms": duration_ms, "error": "no_output"},
            )
