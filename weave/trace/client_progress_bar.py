"""Progress bar utilities for WeaveClient.

This module provides functionality for displaying progress bars when flushing
tasks in the WeaveClient.
"""

import time
from typing import Optional

import tqdm
from weave.trace.concurrent.futures import FutureExecutor


def flush_with_progress_bar(
    main_executor: FutureExecutor,
    fastlane_executor: Optional[FutureExecutor] = None,
) -> None:
    """Flush tasks with a progress bar.

    Args:
        main_executor: The main executor.
        fastlane_executor: The fastlane executor, if any.

    """
    # Get initial count of pending jobs
    initial_main_jobs = main_executor.num_outstanding_futures
    initial_fastlane_jobs = 0
    if fastlane_executor:
        initial_fastlane_jobs = fastlane_executor.num_outstanding_futures

    total_initial_jobs = initial_main_jobs + initial_fastlane_jobs

    if total_initial_jobs > 0:
        print(f"Flushing {total_initial_jobs} pending tasks...")

        # Create progress bar
        with tqdm.tqdm(
            total=total_initial_jobs, desc="Flushing tasks", dynamic_ncols=True
        ) as pbar:
            # Track previous counts to update progress bar correctly
            prev_main_jobs = initial_main_jobs
            prev_fastlane_jobs = initial_fastlane_jobs
            max_total_jobs = total_initial_jobs
            total_completed = 0

            # Monitor progress while jobs are still pending
            while main_executor.num_outstanding_futures > 0 or (
                fastlane_executor and fastlane_executor.num_outstanding_futures > 0
            ):

                # Update progress bar based on completed jobs
                current_main_jobs = main_executor.num_outstanding_futures
                current_fastlane_jobs = 0
                if fastlane_executor:
                    current_fastlane_jobs = fastlane_executor.num_outstanding_futures

                current_total_jobs = current_main_jobs + current_fastlane_jobs

                # If new jobs were added, update the total
                if current_total_jobs > max_total_jobs - total_completed:
                    new_jobs = current_total_jobs - (max_total_jobs - total_completed)
                    max_total_jobs += new_jobs
                    pbar.total = max_total_jobs
                    pbar.refresh()

                # Calculate completed jobs since last update
                main_completed = max(0, prev_main_jobs - current_main_jobs)
                fastlane_completed = max(0, prev_fastlane_jobs - current_fastlane_jobs)
                completed_this_iteration = main_completed + fastlane_completed

                # Update progress bar
                if completed_this_iteration > 0:
                    pbar.update(completed_this_iteration)
                    total_completed += completed_this_iteration

                # Calculate and display progress percentage
                progress_percentage = (
                    (total_completed / max_total_jobs) * 100
                    if max_total_jobs > 0
                    else 0
                )

                # Update progress bar description with remaining jobs and percentage
                job_details = []
                if current_main_jobs > 0:
                    job_details.append(f"{current_main_jobs} main")
                if current_fastlane_jobs > 0:
                    job_details.append(f"{current_fastlane_jobs} file-upload")

                job_details_str = ", ".join(job_details) if job_details else "none"
                pbar.set_description(
                    f"Flushing tasks ({current_total_jobs} remaining: {job_details_str})"
                )

                # Store current counts for next iteration
                prev_main_jobs = current_main_jobs
                prev_fastlane_jobs = current_fastlane_jobs

                # Sleep briefly to allow background threads to make progress
                time.sleep(0.1)
