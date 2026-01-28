"""Base driver protocol for sandbox execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.schema import DriverConfig


@dataclass
class JobResult:
    """Result from a job execution."""

    exit_code: int
    artifacts_path: Path
    duration_seconds: float
    stdout: str = ""
    stderr: str = ""
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and self.error is None


@dataclass
class ImageBuildResult:
    """Result from building a container image."""

    image_id: str
    build_logs: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


class Driver(ABC):
    """Abstract base class for sandbox execution drivers."""

    @abstractmethod
    async def build_image(
        self,
        base_image: str,
        layers: list[Path],
        skill_path: Path,
        adapter_script: Path | None,
        setup_commands: list[str],
        tag: str | None = None,
    ) -> ImageBuildResult:
        """Build a container image for harness execution.

        Args:
            base_image: Base Docker image to build from.
            layers: Additional filesystem layers to copy in.
            skill_path: Path to skill directory to mount.
            adapter_script: Path to harness adapter script.
            setup_commands: Commands to run during image build.
            tag: Optional tag for the built image.

        Returns:
            ImageBuildResult with image ID or error.
        """
        ...

    @abstractmethod
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
        """Run a job in a container.

        Args:
            image: Docker image ID or tag.
            command: Command to execute.
            env: Environment variables to pass.
            timeout: Timeout in seconds.
            artifacts_dir: Directory to store artifacts.
            network_allowlist: Optional list of allowed hosts.
            workdir: Working directory inside container.
            use_host_network: Use host network for API access (default True).

        Returns:
            JobResult with exit code and artifacts path.
        """
        ...

    @abstractmethod
    async def cleanup(self, image: str) -> None:
        """Clean up resources for an image.

        Args:
            image: Docker image ID to clean up.
        """
        ...


def create_driver(config: DriverConfig) -> Driver:
    """Factory function to create a driver from config.

    Args:
        config: Driver configuration.

    Returns:
        Appropriate Driver instance.

    Raises:
        ValueError: If driver type is not supported.
    """
    from ..config.schema import DriverType
    from .docker import DockerDriver

    if config.type == DriverType.DOCKER:
        return DockerDriver(docker_host=config.docker_host)
    elif config.type == DriverType.MODAL:
        raise NotImplementedError("Modal driver not yet implemented")
    else:
        raise ValueError(f"Unknown driver type: {config.type}")
