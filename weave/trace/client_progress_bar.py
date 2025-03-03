"""Progress bar utilities for WeaveClient.

This module provides functionality for displaying progress bars when flushing
tasks in the WeaveClient.
"""

from typing import Callable, TypedDict

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)


class WeaveFlushStatus(TypedDict):
    """Status information about the current flush operation."""

    # Current job counts
    main_jobs: int
    fastlane_jobs: int
    call_processor_jobs: int
    total_jobs: int

    # Tracking of completed jobs
    completed_since_last_update: int
    total_completed: int

    # Maximum number of jobs seen during this flush operation
    max_total_jobs: int

    # Whether there are any pending jobs
    has_pending_jobs: bool


def create_progress_bar_callback() -> Callable[[WeaveFlushStatus], None]:
    """Create a callback function that displays a progress bar for flush status.

    Returns:
        A callback function that can be passed to WeaveClient._flush.
    """
    console = Console()

    # Create a progress bar instance
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=None, complete_style="magenta"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        refresh_per_second=10,
        expand=True,
        transient=False,
    )

    # Start the progress display
    progress.start()

    # Create a task for tracking progress
    task_id = None

    def progress_callback(status: WeaveFlushStatus) -> None:
        """Update the progress bar based on the flush status.

        Args:
            status: The current flush status.
        """
        nonlocal task_id

        # If this is the first update, create the task
        if task_id is None:
            if status["max_total_jobs"] == 0:
                # No jobs to track, just return
                progress.stop()
                return

            # Print initial message
            if not progress.live.is_started:
                print(f"Flushing {status['max_total_jobs']} pending tasks...")

            # Create the task
            task_id = progress.add_task(
                "Flushing tasks", total=status["max_total_jobs"]
            )

        # If there are no more pending jobs, complete the progress bar
        if not status["has_pending_jobs"]:
            progress.update(task_id, completed=status["max_total_jobs"])
            progress.stop()
            return

        # If new jobs were added, update the total
        if status["max_total_jobs"] > progress.tasks[task_id].total:
            progress.update(task_id, total=status["max_total_jobs"])

        # Update progress bar with completed jobs
        if status["completed_since_last_update"] > 0:
            progress.update(task_id, advance=status["completed_since_last_update"])

        # Format job details for description
        job_details = []
        if status["main_jobs"] > 0:
            job_details.append(f"{status['main_jobs']} main")
        if status["fastlane_jobs"] > 0:
            job_details.append(f"{status['fastlane_jobs']} file-upload")
        if status["call_processor_jobs"] > 0:
            job_details.append(f"{status['call_processor_jobs']} call-batch")

        job_details_str = ", ".join(job_details) if job_details else "none"

        # Update progress bar description
        progress.update(
            task_id,
            description=f"Flushing tasks ({status['total_jobs']} remaining: {job_details_str})",
        )

    return progress_callback
