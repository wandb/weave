from weave import cache

import logging
import time
import os

logger = logging.getLogger(__name__)

# Script to run to delete expired caches
if __name__ == "__main__":
    logger.info("Starting clear cache job")
    hour_interval = int(os.getenv("WEAVE_CACHE_CLEAR_INTERVAL", 2))
    logger.info("Clearing expiredcaches  every " + str(hour_interval) + " hours")
    while True:
        curTime = time.strftime("%x, %X", time.localtime())
        logger.info("Clearing cache " + curTime)
        cache.clear_cache()
        time.sleep(60*60*hour_interval)

