"""Docker driver for sandbox execution."""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import time
from pathlib import Path

from .base import Driver, ImageBuildResult, JobResult


class DockerDriver(Driver):
    """Docker-based sandbox driver."""

    def __init__(self, docker_host: str | None = None):
        self.docker_host = docker_host
        self._docker_cmd = ["docker"]
        if docker_host:
            self._docker_cmd.extend(["-H", docker_host])

    async def _run_cmd(
        self, args: list[str], timeout: int | None = None
    ) -> tuple[int, str, str]:
        """Run a docker command asynchronously."""
        cmd = self._docker_cmd + args
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            return proc.returncode or 0, stdout.decode(), stderr.decode()
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return -1, "", "Command timed out"

    async def build_image(
        self,
        base_image: str,
        layers: list[Path],
        skill_path: Path,
        adapter_script: Path | None,
        setup_commands: list[str],
        tag: str | None = None,
    ) -> ImageBuildResult:
        """Build a container image for harness execution."""
        build_logs: list[str] = []

        # Create temporary build context
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = Path(tmpdir)

            # Copy skill to context
            skill_dest = ctx / "skill"
            shutil.copytree(skill_path, skill_dest)
            build_logs.append(f"Copied skill from {skill_path}")

            # Copy layers to context
            for i, layer in enumerate(layers):
                layer_dest = ctx / f"layer_{i}"
                if layer.is_dir():
                    shutil.copytree(layer, layer_dest)
                else:
                    shutil.copy2(layer, layer_dest)
                build_logs.append(f"Copied layer {i} from {layer}")

            # Copy adapter script if provided
            adapter_filename = None
            if adapter_script and adapter_script.exists():
                adapter_filename = adapter_script.name
                shutil.copy2(adapter_script, ctx / adapter_filename)
                build_logs.append(f"Copied adapter from {adapter_script}")

            # Generate Dockerfile
            dockerfile_lines = [
                f"FROM {base_image}",
                "",
                "# Create directories",
                "RUN mkdir -p /workspace /artifacts /workspace/.codex/skills",
                "",
                "# Copy skill to both /skill (generic) and .codex/skills (for Codex CLI)",
                "COPY skill /skill",
                "COPY skill /workspace/.codex/skills/",
                "",
            ]

            # Copy layers
            for i, _ in enumerate(layers):
                dockerfile_lines.append(f"COPY layer_{i} /workspace/")

            # Copy adapter if present
            if adapter_filename:
                # Determine destination filename (preserve original name for clarity)
                dest_name = adapter_filename
                dockerfile_lines.extend([
                    "",
                    "# Copy adapter script",
                    f"COPY {adapter_filename} /usr/local/bin/{dest_name}",
                    f"RUN chmod +x /usr/local/bin/{dest_name}",
                ])

            # Run setup commands
            if setup_commands:
                dockerfile_lines.append("")
                dockerfile_lines.append("# Setup commands")
                for cmd in setup_commands:
                    dockerfile_lines.append(f"RUN {cmd}")

            dockerfile_lines.extend([
                "",
                "WORKDIR /workspace",
            ])

            dockerfile = "\n".join(dockerfile_lines)
            (ctx / "Dockerfile").write_text(dockerfile)
            build_logs.append("Generated Dockerfile")

            # Build the image
            build_args = ["build", "-q"]
            if tag:
                build_args.extend(["-t", tag])
            build_args.append(str(ctx))

            returncode, stdout, stderr = await self._run_cmd(build_args, timeout=600)

            if returncode != 0:
                # Include more context in the error
                error_msg = f"Build failed (exit code {returncode})"
                if stderr:
                    # Truncate stderr if too long
                    stderr_preview = stderr[:1000] + "..." if len(stderr) > 1000 else stderr
                    error_msg += f": {stderr_preview}"
                return ImageBuildResult(
                    image_id="",
                    build_logs=build_logs,
                    error=error_msg,
                )

            image_id = stdout.strip()
            build_logs.append(f"Built image: {image_id}")

            return ImageBuildResult(image_id=image_id, build_logs=build_logs)

    async def run_job(
        self,
        image: str,
        command: list[str],
        env: dict[str, str],
        timeout: int,
        artifacts_dir: Path,
        network_allowlist: list[str] | None = None,
        workdir: str = "/workspace",
        use_host_network: bool = True,
    ) -> JobResult:
        """Run a job in a container."""
        start_time = time.time()
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Build docker run command
        run_args = ["run", "--rm"]

        # Use host network for reliable API access
        # This is necessary because some CLI tools (like Codex) have issues
        # with Docker's default bridge network DNS resolution
        if use_host_network:
            run_args.append("--network=host")

        # Environment variables
        for key, value in env.items():
            run_args.extend(["-e", f"{key}={value}"])

        # Mount artifacts directory
        run_args.extend(["-v", f"{artifacts_dir.absolute()}:/artifacts"])

        # Working directory
        run_args.extend(["-w", workdir])

        # Image and command
        run_args.append(image)
        run_args.extend(command)

        returncode, stdout, stderr = await self._run_cmd(run_args, timeout=timeout)
        duration = time.time() - start_time

        # Write metadata
        metadata = {
            "exit_code": returncode,
            "duration_seconds": duration,
            "command": command,
            "image": image,
        }
        (artifacts_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

        # Copy workspace to artifacts if container exited
        # (workspace is already in artifacts via volume mount for trajectory)

        error = None
        if returncode == -1:
            error = "Job timed out"
        elif returncode != 0:
            error = f"Job failed with exit code {returncode}"
            if stderr:
                stderr_preview = stderr[:500] + "..." if len(stderr) > 500 else stderr
                error += f": {stderr_preview}"

        return JobResult(
            exit_code=returncode,
            artifacts_path=artifacts_dir,
            duration_seconds=duration,
            stdout=stdout,
            stderr=stderr,
            error=error,
        )

    async def cleanup(self, image: str) -> None:
        """Clean up resources for an image."""
        await self._run_cmd(["rmi", "-f", image])
