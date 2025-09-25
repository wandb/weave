# Username Override Feature

This feature allows users to provide an alternate username to override the one specified by their API key. This is particularly useful when using a service account API key while still needing to identify individual users.

## Overview

The username override feature enables:
- Using a single service account API key across multiple users
- Identifying individual users despite using a shared API key
- Maintaining user attribution in traces and logs

## Usage

### Method 1: Environment Variable (for regular Weave traces)

Set the `WEAVE_USER_ID` environment variable before running your application:

```bash
export WEAVE_USER_ID="john_doe_123"
python your_app.py
```

This will override the username for all traces created by the Weave client.

### Method 2: OTEL Span Attribute (for OpenTelemetry traces)

When creating OpenTelemetry spans, include the `wandb.wb_user_id` attribute:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span(
    "my_operation",
    attributes={
        "wandb.wb_user_id": "jane_smith_456"
    }
) as span:
    # Your traced code here
    pass
```

## Implementation Details

The feature is implemented through the following changes:

1. **Environment Variable Support** (`weave/trace/env.py`):
   - Added `weave_user_id_override()` function to read `WEAVE_USER_ID` environment variable

2. **Weave Client Integration** (`weave/trace/weave_client.py`):
   - Modified `create_call` to check for and use the environment variable override

3. **OTEL Support** (`weave/trace_server/opentelemetry/constants.py`):
   - Added `wb_user_id` to `WB_KEYS` mapping to support the `wandb.wb_user_id` attribute

4. **OTEL Processing** (`weave/trace_server/opentelemetry/python_spans.py`):
   - Modified `to_call` method to check for and use the `wandb.wb_user_id` attribute override

## Use Cases

1. **Service Account with Multiple Users**: 
   - Deploy an application using a service account API key
   - Set `WEAVE_USER_ID` based on the authenticated user in your application
   - Each user's traces will be properly attributed

2. **CI/CD Pipelines**:
   - Use a service account for automated testing
   - Override with developer usernames for debugging

3. **Multi-tenant Applications**:
   - Use tenant IDs or customer identifiers as user IDs
   - Maintain clear separation of traces per tenant

## Testing

Run the test script to verify the functionality:

```bash
export WEAVE_USER_ID="test_user"
python test_user_override.py
```

Check the Weave UI to confirm that traces are associated with the overridden username rather than the API key's default user.