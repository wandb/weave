# Weave Offline Mode

Weave now supports an offline mode that allows you to continue logging traces even when you don't have network connectivity. All traces are saved locally in compressed JSON files and can be synced to the server when you're back online.

## Features

- **Local Storage**: All traces are saved to local disk in JSON Lines format
- **Compression**: Files are automatically compressed with gzip to save space
- **Automatic Rotation**: Files are automatically rotated when they reach size limits
- **Batch Syncing**: Sync all offline data at once when back online
- **Project Organization**: Data is organized by entity and project for easy management

## Quick Start

### 1. Initialize in Offline Mode

```python
import weave

# Initialize Weave in offline mode
client = weave.init(
    project_name="my_team/my_project",
    offline=True,
    offline_dir="./offline_data"  # Optional, defaults to ~/.weave/offline
)
```

### 2. Use Weave Normally

```python
@weave.op
def my_function(x: int, y: int) -> int:
    return x + y

# This will be logged locally instead of sent to server
result = my_function(3, 4)
```

### 3. Sync When Back Online

```python
# First, initialize Weave normally (requires authentication)
weave.init("my_team/my_project")

# Then sync your offline data
results = weave.sync_offline_data(
    offline_dir="./offline_data",
    project_name="my_team/my_project"  # Optional, syncs all if not specified
)

print(f"Synced {results['my_team/my_project']['calls'][0]} calls")
```

## Configuration Options

### Offline Directory

By default, offline data is stored in `~/.weave/offline`. You can customize this:

```python
weave.init(project_name="my_project", offline=True, offline_dir="/custom/path")
```

### File Compression

Files are compressed by default to save space. The OfflineTraceServer supports:
- Automatic gzip compression
- Configurable file size limits (default 100MB per file)
- Automatic file rotation when size limits are reached

## Data Organization

Offline data is organized in a hierarchical structure:

```
offline_dir/
├── entity_name/
│   └── project_name/
│       ├── calls/          # Operation traces
│       ├── ops/            # Operation definitions
│       ├── objects/        # Saved objects
│       ├── tables/         # Table data
│       ├── feedback/       # Feedback data
│       ├── files/          # Binary files
│       └── metadata/       # Project metadata
```

Each data type is stored in separate directories with timestamped files:
- `YYYYMMDD_0000.jsonl.gz` - Compressed JSON Lines files
- `YYYYMMDD_0000.synced.jsonl.gz` - Files that have been synced

## Sync Process

The sync process:
1. Reads all unsync'd files from the offline directory
2. Reconstructs the original API calls
3. Sends them to the remote server in the correct order
4. Marks files as synced upon successful upload
5. Returns statistics about what was synced

### Sync All Projects

```python
# Sync all offline data
results = weave.sync_offline_data(offline_dir="./offline_data")

for entity_project, stats in results.items():
    print(f"{entity_project}:")
    for data_type, (synced, errors) in stats.items():
        print(f"  {data_type}: {synced} synced, {errors} errors")
```

### Sync Specific Project

```python
# Sync only a specific project
results = weave.sync_offline_data(
    offline_dir="./offline_data",
    project_name="my_team/my_project"
)
```

### Clean Up Old Synced Files

```python
from weave.trace.offline_sync import OfflineDataSyncer
from weave.trace.weave_init import init_weave_get_server

remote_server = init_weave_get_server()
syncer = OfflineDataSyncer(remote_server, offline_dir="./offline_data")

# Delete synced files older than 7 days
deleted_count = syncer.clean_synced_files(older_than_days=7)
print(f"Deleted {deleted_count} old synced files")
```

## Use Cases

### 1. Edge Deployments

Deploy ML models to edge devices that may have intermittent connectivity:

```python
# On edge device with unreliable network
weave.init("edge_project", offline=True)

@weave.op
def process_sensor_data(data):
    # Process data locally
    return results

# Later, when connected
weave.sync_offline_data()
```

### 2. Field Research

Collect data in remote locations without internet:

```python
# In the field
weave.init("research_project", offline=True)

@weave.op
def analyze_sample(sample_id, measurements):
    # Log analysis locally
    return analysis

# Back at base with internet
weave.init("research_project")
weave.sync_offline_data()
```

### 3. Development and Testing

Develop and test without requiring authentication:

```python
# During development
weave.init("dev_project", offline=True)

# Test your ops without network calls
@weave.op
def experimental_function(x):
    return x * 2

# Later sync if you want to share results
weave.sync_offline_data()
```

## Limitations

Currently, the offline mode has some limitations:

1. **Read Operations**: Operations like `weave.get()` or querying existing data won't work offline
2. **Real-time Collaboration**: Team members won't see your traces until you sync
3. **File Storage**: Binary files (images, etc.) are stored locally and may consume significant disk space

## Troubleshooting

### Files Not Syncing

If files aren't syncing:
1. Check that you're authenticated: `weave.init("project")` before syncing
2. Verify the offline directory path is correct
3. Check file permissions on the offline directory
4. Look for `.synced` extensions - these files have already been uploaded

### Disk Space Issues

To manage disk space:
1. Regularly sync and clean old files
2. Set smaller file size limits when initializing OfflineTraceServer
3. Use a dedicated partition for offline data
4. Monitor the offline directory size

### Sync Errors

If sync encounters errors:
1. Check network connectivity
2. Verify authentication credentials
3. Check server API compatibility
4. Review error logs for specific issues
5. Partial syncs are safe - you can retry failed items

## API Reference

### `weave.init()`

```python
weave.init(
    project_name: str,
    offline: bool = False,
    offline_dir: str | None = None,
    ...
)
```

- `offline`: Enable offline mode
- `offline_dir`: Directory for offline data (default: `~/.weave/offline`)

### `weave.sync_offline_data()`

```python
weave.sync_offline_data(
    offline_dir: str | None = None,
    project_name: str | None = None,
    api_key: str | None = None
) -> dict
```

- `offline_dir`: Directory containing offline data
- `project_name`: Specific project to sync (optional)
- `api_key`: API key for authentication (optional)
- Returns: Dictionary with sync statistics

## Examples

See the [offline_mode_example.py](../examples/offline_mode_example.py) for a complete working example.