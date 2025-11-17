"""Progress bar utilities for WeaveClient.

This module provides functionality for displaying progress bars when flushing
tasks in the WeaveClient.
"""

import logging
from collections.abc import Callable

from weave.trace.display import display
from weave.trace.weave_client import FlushStatus

logger = logging.getLogger(__name__)


def create_progress_bar_callback() -> Callable[[FlushStatus], None]:
    """Create a callback function that displays a progress bar for flush status.

    Returns:
        A callback function that can be passed to WeaveClient._flush.
    """
    console = display.Console()

    # Create a progress bar instance
    progress = display.Progress(
        console=console,
        refresh_per_second=10,
    )

    # Start the progress display
    progress.start()

    # Create a task for tracking progress
    task_id = None
    current_total = 0
    first_update = True

    def progress_callback(status: FlushStatus) -> None:
        """Update the progress bar based on the flush status.

        Args:
            status: The current flush status.
        """
        nonlocal task_id, current_total, first_update

        counts = status["job_counts"]

        # If this is the first update, create the task
        if task_id is None:
            if counts["total_jobs"] == 0:
                # No jobs to track, just return
                progress.stop()
                return

            # Print initial message
            if first_update:
                logger.info(f"Flushing {counts['total_jobs']} pending tasks...")
                first_update = False

            # Create the task
            task_id = progress.add_task("Flushing tasks", total=counts["total_jobs"])
            current_total = counts["total_jobs"]

        # If there are no more pending jobs, complete the progress bar
        if not status["has_pending_jobs"]:
            progress.update(
                task_id,
                completed=status["max_total_jobs"],
                total=status["max_total_jobs"],
            )
            progress.stop()
            return

        # If new jobs were added, update the total
        if status["max_total_jobs"] > current_total:
            progress.update(task_id, total=status["max_total_jobs"])
            current_total = status["max_total_jobs"]

        # Update progress bar with completed jobs
        if status["completed_since_last_update"] > 0:
            progress.update(task_id, advance=status["completed_since_last_update"])

        # Format job details for description
        job_details = []
        if counts["main_jobs"] > 0:
            job_details.append(f"{counts['main_jobs']} main")
        if counts["fastlane_jobs"] > 0:
            job_details.append(f"{counts['fastlane_jobs']} file-upload")
        if counts["call_processor_jobs"] > 0:
            job_details.append(f"{counts['call_processor_jobs']} call-batch")
        if counts["feedback_processor_jobs"] > 0:
            job_details.append(f"{counts['feedback_processor_jobs']} feedback-batch")

        job_details_str = ", ".join(job_details) if job_details else "none"

        # Update progress bar description
        progress.update(
            task_id,
            description=f"Flushing tasks ({counts['total_jobs']} remaining: {job_details_str})",
        )

    return progress_callback
