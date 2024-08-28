# Test script that downloads a bunch of files from a wandb artifact.
# Shows how to configure the various async APIs we use for WeaveIOManager.
# I had this up to 25MB/s download speed on the dsviz artifact (on both
# a gcp machine and a local network). Its probably slower now as I've
# added a bunch of features to the libraries without testing perf at
# this level, like safe file download and renaming.
#
# Try setting http.TRACE=True when you run this.
#
# Run from repo root with: `python -m weave.test_scripts.wandb_artifact_perf`

import asyncio
import cProfile
import time

from weave.legacy.weave import (
    artifact_wandb,
    async_map,
    engine_trace,
    filesystem,
    wandb_api,
    wandb_file_manager,
    weave_http,
)

tracer = engine_trace.tracer()  # type: ignore


async def gql_test() -> None:
    api = await wandb_api.get_wandb_api()
    fs = filesystem.get_filesystem_async()
    net = weave_http.HttpAsync(fs)
    file_man = wandb_file_manager.WandbFileManagerAsync(fs, net, api)
    man = await file_man.manifest(
        artifact_wandb.WeaveWBArtifactURI(
            "raw_data",
            "v4",
            entity_name="shawn",
            project_name="dsviz_demo",
        )
    )
    if man is None:
        raise Exception("Manifest is None")
    result_paths = []
    start_time = time.time()
    with cProfile.Profile() as profile:
        paths = list(man.get_paths_in_directory(""))[:1000]
        uris = [
            artifact_wandb.WeaveWBArtifactURI(
                "raw_data",
                "v4",
                entity_name="shawn",
                project_name="dsviz_demo",
                path=p,
            )
            for p in paths
        ]
        result_paths = await async_map.map_with_parallel_workers(
            uris, file_man.ensure_file, max_parallel=200
        )
    total_time = time.time() - start_time
    total_size = 0

    print("Downloaded N files:", len(result_paths))
    for path in result_paths:
        if path is None:
            raise Exception("Got none path")
        total_size += await fs.getsize(path)
    print(
        f"Downloaded {total_size} bytes in {total_time}s. {total_size / (1024**2) / total_time} MB/s"
    )

    profile.dump_stats("/tmp/profile.prof")


if __name__ == "__main__":
    asyncio.run(gql_test())
