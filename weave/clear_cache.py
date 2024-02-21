from weave import cache

import time
import os


# Script to run to delete expired caches
if __name__ == "__main__":
    print("Starting clear cache job")
    hour_interval = int(os.getenv("WEAVE_CACHE_CLEAR_INTERVAL", 2))
    print("Clearing expiredcaches  every " + str(hour_interval) + " hours")
    while True:
        curTime = time.strftime("%x, %X", time.localtime())
        print("Clearing cache " + curTime)
        cache.clear_cache()
        time.sleep(60*60*hour_interval)

