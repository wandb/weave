# DO NOT MOVE OR DELETE OR RENAME THIS FILE
# This file is used by the clear_cache job in the weave-python helm chart
# https://github.com/wandb/helm-charts/blob/fe97ad11ddbbfb4cf3e9b05888ea8a3ab43518a6/charts/operator-wandb/charts/weave/templates/deployment.yaml#L93
# The plan is to keep this file around for a while to make sure we dont introduce and back compat issues, while moving weave-python
# TODO: Josiah, remove this file when we have confirmed that the new clear_cache job in weave-python dedicated is working as expected
import os
import time

from weave.legacy.weave import cache

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
