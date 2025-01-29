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

## Server Response Caching (Experimental)

If you're experiencing performance issues with repeated queries or have limited network bandwidth, you can enable server response caching. 

:::note
This feature is currently experimental and will become the default once stabilized.
:::

### When to Use Caching

Consider enabling caching when:
- You frequently run the same queries
- You have limited network bandwidth
- You're working in an environment with high latency
- You're developing offline and want to cache responses for later use

This feature is specifically useful when running repeated evaluations on a dataset in order to cache the dataset between runs.

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

