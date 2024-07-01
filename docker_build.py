#!/usr/bin/env python3
#
# This is a copy of docker_build.py from wandb/core

import argparse
import os
import subprocess
import sys
from typing import Dict, List, Optional


def exec_read(cmd: str) -> str:
    try:
        proc = subprocess.run(cmd, shell=True, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(e.stdout)
        print(e.stderr)
        raise e

    return proc.stdout.decode("utf-8").rstrip()


def exec_stream(cmd: str):
    return subprocess.run(
        cmd.replace("\n", "").replace("\\", ""), shell=True, check=True
    )


def print_green(msg):
    print("\033[92m\033[1m{}\033[00m\n".format(msg))


DIRTY = "-dirty" if exec_read("git status -s") != "" else ""

GIT_SHA = exec_read("git describe --match= --always --abbrev=40")
GIT_SHA_DIRTY = GIT_SHA + DIRTY  # will be $GIT_SHA if repository is not dirty
GIT_BRANCH = exec_read("git rev-parse --abbrev-ref HEAD").replace("/", "-")
GIT_BRANCH_DIRTY = GIT_BRANCH + DIRTY  # will be $GIT_BRANCH if repository is not dirty
GIT_PARENT_SHA = exec_read("git describe --match= --always --abbrev=40 HEAD^")
REGISTRY = os.getenv("REGISTRY", "gcr.io/wandb-production")
NO_CACHE = bool(os.getenv("NO_CACHE", False))
CI = bool(os.getenv("CI", False))
BUILD_DATE = exec_read("date +%Y-%m-%d")

# Target Tags:
#
# WIP commits will get :SHA-dirty and :branch-dirty, whereas builds from clean
# commits will get :SHA and :branch
WRITE_TAGS = [GIT_SHA_DIRTY, GIT_BRANCH_DIRTY]


def check_exists(qualified_image: str):
    print_green(f"Checking that {qualified_image} exists...")

    exists_command = f"docker buildx imagetools inspect {qualified_image}"

    if not CI:
        # in a local build, the image won't exist in the registry,
        # so we only check if it exists locally
        exists_command = f"docker image inspect -f 'image exists' {qualified_image}"

    print(exists_command)
    exec_stream(exists_command)


def qualified_image_name(image: str, tag: str) -> str:
    return f"{REGISTRY}/{image}:{tag}"


def _build_common(
    image: str, context_path: str, dockerfile: str, platform: str = "linux/amd64"
) -> str:
    command = f"docker buildx build {context_path}"
    command += f" \ \n  --file={dockerfile}"

    command += f" \ \n  --platform={platform}"

    # This line tells BuildKit to include metadata so that all layers of the
    # result image can be used as a cache source when pulled from the registry.
    # Note that this DOES NOT HAPPEN BY DEFAULT: without this flag, the
    # intermediate layers become part of your LOCAL cache, but can't be used
    # as cache from the registry.
    command += " \ \n  --cache-to=type=inline"

    # these options manipulate the output type -- refer to
    # https://docs.docker.com/engine/reference/commandline/buildx_build/#options
    # and https://docs.docker.com/engine/reference/commandline/buildx_build/#output for
    # details
    if CI:
        # Everyone can read from the registry, but only authorized users can push.
        print_green(
            f'Image will be pushed to {REGISTRY}. Set CI="" to load into the local docker daemon.'
        )
        command += " \ \n  --push"
    else:
        # if we're not pushing, we'll assume we want to load the image into the running
        # docker agent (there's really no point to building if you don't do at least one of these two
        # things, since the resultant image would just remain in cache, unusable)
        print_green(
            f"Image will be loaded into the local docker daemon. Set CI=1 to push to {REGISTRY}"
        )
        command += " \ \n  --load"

    return command


CACHE_FROM_TAGS = [
    "latest-deps",
    GIT_SHA_DIRTY,
    GIT_SHA,
    GIT_PARENT_SHA,
    GIT_BRANCH,
    "master",
]


def build(
    image: str,
    context_path: str,
    dockerfile: str,
    cache_from_image: Optional[str] = None,
    extra_write_tags: List[str] = [],
    build_args: Dict[str, str] = {},
    build_contexts: Dict[str, str] = {},
    target: Optional[str] = None,
    platform: str = "linux/amd64",
):
    """
    Builds an image, using previous builds as cache.

    Recent builds of `cache_from_image` will be searched for matching cache layers.
    In most cases, `cache_from_image` will be the same as `image`, but for
    complex multi-stage builds, it's sometimes useful to use an earlier stage
    as the cache source instead.

    Args:
        image: The name of the image to build.
        context_path: The path to the directory to use as the build context.
        dockerfile: The path to the Dockerfile.
        cache_from_image: The name of the image to use as the cache source.
        extra_write_tags: A list of additional tags to apply to the image (in additiion
                    to the standard SHA and branch name tags).
    """
    cache_from_image = cache_from_image if cache_from_image else image

    # Cache Sources:
    #
    # The goal here is to make sure that every build uses a cache from the
    # closest possible successfully-built commit. So:
    #
    # - all builds will try to reference the latest cacheless build (to ensure deps
    #   are up to date)
    # - a rebuild on the same commit will reuse the original build
    # - a build on a WIP commit will start from the clean commit it started from
    # - a build on a newly-committed commit will start from its parent, IF its
    #   parent built successfully
    # - a build on a newly-committed commit will start from the most-recent
    #   successful build on its branch
    # - if all else fails, a build will start from the latest successful master build

    print_green(f"Building {image} at commit {GIT_SHA_DIRTY}...")

    command = _build_common(image, context_path, dockerfile, platform)

    if target:
        command += f" \ \n  --target={target}"

    for arg, value in build_args.items():
        command += f" \ \n  --build-arg {arg}={value}"

    for name, context in build_contexts.items():
        command += f" \ \n  --build-context {name}={context}"

    if NO_CACHE:
        command += "\ \n  --no-cache"
    else:
        for tag in CACHE_FROM_TAGS:
            full_name = qualified_image_name(cache_from_image, tag)
            command += f" \ \n  --cache-from={full_name}"

    for tag in WRITE_TAGS + extra_write_tags:
        full_name = qualified_image_name(image, tag)
        command += f" \ \n  --tag={full_name}"

    if not CI:
        # development tooling sometimes looks for service:latest, so we should
        # make sure that we tag newly-built images that way when building for
        # local development
        print_green("Because CI==False, image will also be tagged `latest`")
        full_name = qualified_image_name(image, "latest")
        command += f" \ \n  --tag={full_name}"

    print(command)
    print("")

    exec_stream(command)


def build_cmd(args: argparse.Namespace):
    image = args.image
    context_path = args.context_path
    dockerfile = args.dockerfile if args.dockerfile else f"{context_path}/Dockerfile"

    build(image, context_path, dockerfile)


def build_deps_cmd(args: argparse.Namespace):
    image = args.image
    target = args.target
    context_path = args.context_path
    dockerfile = args.dockerfile if args.dockerfile else f"{context_path}/Dockerfile"
    build_deps(image, target, context_path, dockerfile)


# The intention is that this should run on a regular cadence from master,
# ensuring that all built images start with fairly recent deps.
def build_deps(
    image: str, target: str, context_path: str = ".", dockerfile: Optional[str] = None
):
    dockerfile = dockerfile if dockerfile else f"{context_path}/Dockerfile"

    print_green(f"Building deps for {image} at commit {GIT_SHA_DIRTY}...")

    print_green(
        f"Image will build to target {target} without cache, and push to tag latest-deps"
    )

    command = _build_common(image, context_path, dockerfile)

    command += f" \ \n  --target={target}"

    latest_deps_full_name = qualified_image_name(image, "latest-deps")
    command += f" \ \n  --tag={latest_deps_full_name}"

    for tag in WRITE_TAGS:
        full_name = qualified_image_name(image, tag)
        command += f" \ \n  --tag={full_name}"

    print(command)
    print("")

    exec_stream(command)


def manifest_cmd(args: argparse.Namespace):
    manifest(args.manifest_list_name, args.manifest_names)


def manifest(manifest_list_name: str, manifest_names: List[str]):
    manifest_names_str = " ".join(manifest_names)

    print_green(
        f"Manifest will be generated joining {manifest_names_str} into "
        + f"target {manifest_list_name}"
    )

    # a "manifest list" is a single name that points to multiple image
    # manifests for multi-platform support (e.g. manifest list myimage
    # might point to myimage-arm64 and myimage-amd64). When you
    # `docker run myimage`, Docker will automatically select the image
    # matching the host architecture, if it's available.

    # manifest lists have to be explicitly created and pushed for each
    # individual tag, so we'll iterate over all of our WRITE_TAGS and
    # generate a manifest list for each one, joining the corresponding
    # tags from each of `manifests` to the same tag under `manifest_list`
    for write_tag in WRITE_TAGS:
        print_green(f"Creating manifest for tag {write_tag}")
        manifest_list_full_name = qualified_image_name(manifest_list_name, write_tag)
        create_command = "docker manifest create " + f"{manifest_list_full_name}"

        for manifest_name in manifest_names:
            manifest_full_name = qualified_image_name(manifest_name, write_tag)
            create_command += f" \ \n  {manifest_full_name}"

        push_command = "docker manifest push " + f"{manifest_list_full_name}"

        print(create_command)
        print(push_command)
        print("")

        exec_stream(create_command)
        exec_stream(push_command)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="wandb utilities for interacting with docker images"
    )

    subparsers = parser.add_subparsers(title="commands")

    build_parser = subparsers.add_parser(
        "build", help="builds an image using builds from the registry as cache"
    )
    build_parser.add_argument("image", type=str)
    build_parser.add_argument("context_path", type=str, nargs="?", default=".")
    build_parser.add_argument("dockerfile", type=str, nargs="?", default=None)
    build_parser.set_defaults(func=build_cmd)

    deps_parser = subparsers.add_parser(
        "build_deps",
        help="builds a partial image, without cache, for other builds to "
        + "use as a dependency cache",
    )
    deps_parser.add_argument("image", type=str)
    deps_parser.add_argument("target", type=str)
    deps_parser.add_argument("context_path", type=str, nargs="?", default=".")
    deps_parser.add_argument("dockerfile", type=str, nargs="?", default=None)
    deps_parser.set_defaults(func=build_deps_cmd)

    manifest_parser = subparsers.add_parser(
        "manifest", help="joins multiple images under one name"
    )
    manifest_parser.add_argument(
        "manifest_list_name",
        type=str,
        help="target name for the joined image (e.g. 'myimage')",
    )
    manifest_parser.add_argument(
        "manifest_names",
        type=str,
        nargs="+",
        help="names of the images to join (e.g. 'myimage-amd64' 'myimage-arm64)",
    )
    manifest_parser.set_defaults(func=manifest)

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()
    args.func(args)
