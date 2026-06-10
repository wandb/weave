#!/usr/bin/env bash
# Fetch the ClickHouse server binary used by the clickhouse-local test backend
# (`pytest --trace-server=clickhouse-local`). Idempotent: skips the download
# when the pinned version is already cached. Prints the absolute binary path
# on stdout; all diagnostics go to stderr.
set -euo pipefail

# Pinned version for Linux (CI). Keep the minor in sync with the docker tag in
# .github/scripts/ch-image.sh so the binary and the remaining dockerized jobs
# (migrator topologies) exercise the same ClickHouse minor.
CLICKHOUSE_VERSION="${CLICKHOUSE_VERSION:-26.4.4.38}"
CACHE_DIR="${WEAVE_CLICKHOUSE_CACHE_DIR:-${HOME}/.cache/weave-clickhouse}"

dest_dir="${CACHE_DIR}/${CLICKHOUSE_VERSION}"
dest="${dest_dir}/clickhouse"

if [ -x "$dest" ]; then
  echo "Using cached ClickHouse at ${dest}" >&2
  echo "$dest"
  exit 0
fi

os="$(uname -s)"
arch="$(uname -m)"
mkdir -p "$dest_dir"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

case "$os" in
  Linux)
    case "$arch" in
      x86_64) pkg_arch="amd64" ;;
      aarch64 | arm64) pkg_arch="arm64" ;;
      *)
        echo "Unsupported architecture: ${arch}" >&2
        exit 1
        ;;
    esac
    url="https://packages.clickhouse.com/tgz/stable/clickhouse-common-static-${CLICKHOUSE_VERSION}-${pkg_arch}.tgz"
    echo "Downloading ${url}" >&2
    curl -fsSL --retry 3 --retry-delay 2 "$url" -o "$tmp/clickhouse.tgz"
    tar -xzf "$tmp/clickhouse.tgz" -C "$tmp"
    # The tarball layout is clickhouse-common-static-<ver>/usr/bin/clickhouse.
    found="$(find "$tmp" -type f -name clickhouse -path '*/usr/bin/*' | head -1)"
    if [ -z "$found" ]; then
      echo "clickhouse binary not found in ${url}" >&2
      exit 1
    fi
    mv "$found" "$dest"
    ;;
  Darwin)
    # No official versioned macOS tarballs exist, so dev machines get the
    # latest build from the official installer (version floats; CI runs the
    # pinned Linux build above). `brew install --cask clickhouse` also works.
    echo "Downloading ClickHouse for macOS via https://clickhouse.com/ (unpinned dev build)" >&2
    (cd "$tmp" && curl -fsSL https://clickhouse.com/ | sh) >&2
    mv "$tmp/clickhouse" "$dest"
    ;;
  *)
    echo "Unsupported OS: ${os}" >&2
    exit 1
    ;;
esac

chmod +x "$dest"
"$dest" --version >&2
echo "$dest"
