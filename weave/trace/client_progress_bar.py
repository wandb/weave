"""Progress bar utilities for WeaveClient.

This module provides functionality for displaying progress bars when flushing
tasks in the WeaveClient.
"""

import time
from typing import Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from weave.trace.concurrent.futures import FutureExecutor


class TaskProgressBar:
    """A class to manage and display progress for task execution.

    This class provides a rich progress bar interface for tracking the execution
    of tasks in the WeaveClient.
    """

    def __init__(
        self,
        main_executor: FutureExecutor,
        fastlane_executor: Optional[FutureExecutor] = None,
    ):
        """Initialize the TaskProgressBar.

        Args:
            main_executor: The main executor for regular tasks.
            fastlane_executor: The fastlane executor for file upload tasks, if any.
        """
        self.main_executor = main_executor
        self.fastlane_executor = fastlane_executor
        self.console = Console()

        # Initialize tracking variables
        self.initial_main_jobs = main_executor.num_outstanding_futures
        self.initial_fastlane_jobs = 0
        if fastlane_executor:
            self.initial_fastlane_jobs = fastlane_executor.num_outstanding_futures

        self.total_initial_jobs = self.initial_main_jobs + self.initial_fastlane_jobs

        # Progress tracking state
        self.prev_main_jobs = self.initial_main_jobs
        self.prev_fastlane_jobs = self.initial_fastlane_jobs
        self.max_total_jobs = self.total_initial_jobs
        self.total_completed = 0

    def _create_progress_instance(self) -> Progress:
        """Create and configure a Rich Progress instance.

        Returns:
            A configured Rich Progress instance.
        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=None, complete_style="magenta"),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
            refresh_per_second=10,
            expand=True,
            transient=False,
        )

    def _get_current_job_counts(self) -> tuple[int, int, int]:
        """Get the current counts of outstanding jobs.

        Returns:
            A tuple containing (current_main_jobs, current_fastlane_jobs, current_total_jobs)
        """
        current_main_jobs = self.main_executor.num_outstanding_futures
        current_fastlane_jobs = 0
        if self.fastlane_executor:
            current_fastlane_jobs = self.fastlane_executor.num_outstanding_futures

        current_total_jobs = current_main_jobs + current_fastlane_jobs
        return current_main_jobs, current_fastlane_jobs, current_total_jobs

    def _calculate_completed_jobs(
        self, current_main_jobs: int, current_fastlane_jobs: int
    ) -> int:
        """Calculate the number of jobs completed since the last update.

        Args:
            current_main_jobs: Current count of main jobs.
            current_fastlane_jobs: Current count of fastlane jobs.

        Returns:
            Number of jobs completed in this iteration.
        """
        main_completed = max(0, self.prev_main_jobs - current_main_jobs)
        fastlane_completed = max(0, self.prev_fastlane_jobs - current_fastlane_jobs)
        return main_completed + fastlane_completed

    def _format_job_details(
        self, current_main_jobs: int, current_fastlane_jobs: int
    ) -> str:
        """Format job details for the progress bar description.

        Args:
            current_main_jobs: Current count of main jobs.
            current_fastlane_jobs: Current count of fastlane jobs.

        Returns:
            Formatted string describing job details.
        """
        job_details = []
        if current_main_jobs > 0:
            job_details.append(f"{current_main_jobs} main")
        if current_fastlane_jobs > 0:
            job_details.append(f"{current_fastlane_jobs} file-upload")

        return ", ".join(job_details) if job_details else "none"

    def _has_pending_jobs(self) -> bool:
        """Check if there are any pending jobs.

        Returns:
            True if there are pending jobs, False otherwise.
        """
        if self.main_executor.num_outstanding_futures > 0:
            return True
        if (
            self.fastlane_executor
            and self.fastlane_executor.num_outstanding_futures > 0
        ):
            return True
        return False

    def run(self) -> None:
        """Run the progress bar to track task execution until completion."""
        if self.total_initial_jobs == 0:
            return

        print(f"Flushing {self.total_initial_jobs} pending tasks...")

        with self._create_progress_instance() as progress:
            # Create a task for tracking progress
            task_id = progress.add_task("Flushing tasks", total=self.total_initial_jobs)

            while self._has_pending_jobs():
                current_main_jobs, current_fastlane_jobs, current_total_jobs = (
                    self._get_current_job_counts()
                )

                # If new jobs were added, update the total
                if current_total_jobs > self.max_total_jobs - self.total_completed:
                    new_jobs = current_total_jobs - (
                        self.max_total_jobs - self.total_completed
                    )
                    self.max_total_jobs += new_jobs
                    progress.update(task_id, total=self.max_total_jobs)

                # Calculate completed jobs since last update
                completed_this_iteration = self._calculate_completed_jobs(
                    current_main_jobs, current_fastlane_jobs
                )

                # Update progress bar
                if completed_this_iteration > 0:
                    progress.update(task_id, advance=completed_this_iteration)
                    self.total_completed += completed_this_iteration

                # Update progress bar description
                job_details_str = self._format_job_details(
                    current_main_jobs, current_fastlane_jobs
                )
                progress.update(
                    task_id,
                    description=f"Flushing tasks ({current_total_jobs} remaining: {job_details_str})",
                )

                # Store current counts for next iteration
                self.prev_main_jobs = current_main_jobs
                self.prev_fastlane_jobs = current_fastlane_jobs

                # Sleep briefly to allow background threads to make progress
                time.sleep(0.1)


def flush_with_progress_bar(
    main_executor: FutureExecutor,
    fastlane_executor: Optional[FutureExecutor] = None,
) -> None:
    """Flush tasks with a progress bar.

    Args:
        main_executor: The main executor.
        fastlane_executor: The fastlane executor, if any.
    """
    progress_bar = TaskProgressBar(main_executor, fastlane_executor)
    progress_bar.run()
