# DO NOT MOVE OR DELETE OR RENAME THIS FILE
# This file is used by the clear_cache job in the weave-python helm chart
# https://github.com/wandb/helm-charts/blob/fe97ad11ddbbfb4cf3e9b05888ea8a3ab43518a6/charts/operator-wandb/charts/weave/templates/deployment.yaml#L93
# The plan is to keep this file around for a while to make sure we dont introduce and back compat issues, while moving weave-python
# TODO: Josiah, remove this file when we have confirmed that the new clear_cache job in weave-python dedicated is working as expected
import os
import time
import shutil
import logging
import datetime

logger = logging.getLogger(__name__)


def weave_filesystem_dir() -> str:
    # WEAVE_LOCAL_ARTIFACT_DIR should be renamed to WEAVE_FILESYSTEM_DIR
    # TODO
    return os.environ.get("WEAVE_LOCAL_ARTIFACT_DIR") or os.path.join(
        "/tmp", "weave", "fs"
    )


def cache_deletion_buffer_days() -> int:
    return int(os.getenv("WEAVE_CACHE_DELETION_BUFFER_DAYS", 1))


def delete_cache_item(directory_path: str, item: str) -> None:
    try:
        item_path = os.path.join(directory_path, item)
        shutil.rmtree(item_path)
        logger.info(f"Deleted {item}.")
    except:
        logger.info(f"Error deleting {item}.")


def clear_cache() -> None:
    # Read the directory address and threshold from the environment variable
    directory_path = weave_filesystem_dir()

    now = datetime.datetime.now().timestamp()
    # buffer is in seconds
    buffer = 60 * 60 * 24 * cache_deletion_buffer_days()  # days of buffer

    # Validate the directory path
    if not directory_path:
        logger.info("WEAVE_PYTHON_CACHE is not set.")
        return
    if not os.path.isdir(directory_path):
        logger.info(f"{directory_path} is not a valid directory.")
        return

    # for each cache in the directory, check if its expired past the buffer
    for item in os.listdir(directory_path):
        try:
            # If parsable timestamp, delete if expired
            item_timestamp = int(item)

            # If the item is expired and we are past the buffer, delete it
            if item_timestamp + buffer < now:
                delete_cache_item(directory_path, item)

        except ValueError:
            # If not parsable timestamp, delete the item, because we have now moved to only timestamped cache directories
            delete_cache_item(directory_path, item)

        except:
            logger.info(f"Error deleting {item}.")
            continue


# Script to run to delete expired caches
if __name__ == "__main__":
    print("Starting clear cache job", flush=True)
    hour_interval = int(os.getenv("WEAVE_CACHE_CLEAR_INTERVAL", 24))
    print("Clearing expired caches every " + str(hour_interval) + " hours", flush=True)
    while True:
        curTime = time.strftime("%x, %X", time.localtime())
        print("Clearing cache " + curTime, flush=True)
        clear_cache()
        time.sleep(60 * 60 * hour_interval)
