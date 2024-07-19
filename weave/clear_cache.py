import os
import time

from weave.legacy import cache

# TODO: This should be split out into a scripts dir
# Script to run to delete expired caches
if __name__ == "__main__":
    print("Starting clear cache job", flush=True)
    hour_interval = int(os.getenv("WEAVE_CACHE_CLEAR_INTERVAL", 24))
    print("Clearing expired caches every " + str(hour_interval) + " hours", flush=True)
    while True:
        curTime = time.strftime("%x, %X", time.localtime())
        print("Clearing cache " + curTime, flush=True)
        cache.clear_cache()
        time.sleep(60 * 60 * hour_interval)
