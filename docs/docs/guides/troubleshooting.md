# Troubleshooting

This page provides solutions and guidance for common issues you may encounter. As we continue to expand this guide, more troubleshooting topics will be added to address a broader range of scenarios.

:::tip
Do you have Weave troubleshooting advice to share with the community? Click **Edit this page** at the bottom of this guide to contribute directly by submitting a pull request.
:::

## Trace pages load slowly

If trace pages are loading slowly, reduce the number of rows displayed to improve load time. The default value is `50`. You can either reduce the number of rows via the UI, or using query parameters.

### Adjust via the UI (recommended)

Use the **Per page** control at the bottom-right of the Traces page to adjust the number of rows displayed. In addition to the default of `50`, you can also set to `10`, `25`, or `100`.

### Use query parameters

If you prefer a manual approach, you can modify the `pageSize` query parameter in your query URL to a value less than the maximum of `100`.

## Server Response Caching

Weave provides server response caching to improve performance when making repeated queries or working with limited network bandwidth. While currently disabled by default, this feature is expected to become the default behavior in a future release.

### When to Use Caching

Server response caching is particularly beneficial when:

- You frequently run the same queries
- You have limited network bandwidth
- You're working in an environment with high latency
- You're developing offline and want to cache responses for later use

This feature is especially useful when running repeated evaluations on a dataset, as it allows caching the dataset between runs.

### How to Enable Caching

To enable caching, you can set the following environment variables:

```bash
# Enable server response caching
export WEAVE_USE_SERVER_CACHE=true

# Set cache size limit (default is 1GB)
export WEAVE_SERVER_CACHE_SIZE_LIMIT=1000000000

# Set cache directory (optional, defaults to temporary directory)
export WEAVE_SERVER_CACHE_DIR=/path/to/cache
```

### Caching Behavior

Technically, this feature will cache idempotent requests against the server. Specifically, we cache:

- `obj_read`
- `table_query`
- `table_query_stats`
- `refs_read_batch`
- `file_content_read`

### Cache Size and Storage Details

The cache size is controlled by `WEAVE_SERVER_CACHE_SIZE_LIMIT` (in bytes). The actual disk space used consists of three components:

1. A constant 32KB checksum file
2. A Write-Ahead Log (WAL) file up to ~4MB per running client (automatically removed when the program exits)
3. The main database file, which is at least 32KB and at most `WEAVE_SERVER_CACHE_SIZE_LIMIT`

Total disk space used:

- While running >= 32KB + ~4MB + cache size
- After exit >= 32KB + cache size

For example, with the a 5MB cache limit:

- While running: ~9MB maximum
- After exit: ~5MB maximum

## Long eval clean up times

The following two methods should be used together in order to improve performance when running evaluations with large datasets.

### Flushing

When running evaluations with large datasets, you may experience a long period of time before program execution, while the dataset is being uploaded in background threads. This generally occurs when main thread execution finished before background cleanup is complete. Calling `client.flush()` will force all background tasks to be processed in the main thread, ensuring parallel processing during main thread execution. This can improve performance when user code completes before data has been uploaded to the server.

Example:

```python
client = weave.init("fast-upload")

# ... evaluation setup
result = evaluation.Evaluate(dataset_id="my_dataset_id")

client.flush()
```

### Increasing client parallelism

Client parallelism is automatically determined based on the environment, but can be set manually using the following environment variable:

- `WEAVE_CLIENT_PARALLELISM`: The number of threads available for parallel processing. Increasing this number will increase the number of threads available for parallel processing, potentially improving the performance of background tasks like dataset uploads.

This can also be set programmatically using the `settings` argument to `weave.init()`:

```python
client = weave.init("fast-upload", settings={"client_parallelism": 100})
```

## OSError: [Errono 24] Too many open files

This error occurs when the number of open files exceeds the limit set by your operating system. In Weave, this may happen because you're working with large image datasets and/or your system has a low limit on the number of open files. Weave uses `PIL` for image processing, which keeps the file descriptors open for the duration of the program.

To resolve this issue, you can increase the limit using the following command:

```bash
ulimit -n 65536
```
