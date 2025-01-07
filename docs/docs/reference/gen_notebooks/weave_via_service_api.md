---
title: Service API
---


:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/weave_via_service_api.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/weave_via_service_api.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::



<!--- @wandbcode{cod-notebook} -->

# Use the Service API to Log and Query Traces

In the following guide, you will learn how to use the Weave Service API to log traces. Specifically, you will use the Service API to:

1. [Create a mock of a simple LLM call and response, and log it to Weave.](#simple-trace)
2. [Create a mock of a more complex LLM call and response, and log it to Weave.](#complex-trace)
3. [Run a sample lookup query on the logged traces.](#run-a-lookup-query)

> **View logged traces**
>
> You can view all of the Weave traces created when you run the code in this guide by going to the **Traces** tab in your Weave project (specified by `team_id\project_id`), and selecting the name of the trace.

Before beginning, complete the [prerequisites](#prerequisites-set-variables-and-endpoints)

## Prerequisites: Set variables and endpoints

The following code sets the URL endpoints that will be used to access the Service API:

- [`https://trace.wandb.ai/call/start`](https://weave-docs.wandb.ai/reference/service-api/call-start-call-start-post)
- [`https://trace.wandb.ai/call/end`](https://weave-docs.wandb.ai/reference/service-api/call-end-call-end-post)
- [`https://trace.wandb.ai/calls/stream_query`](https://weave-docs.wandb.ai/reference/service-api/calls-query-stream-calls-stream-query-post)

Additionally, you must set the following variables:

- `project_id`: The name of the W&B project that you want to log your traces to.
- `team_id`: Your W&B team name.
- `wandb_token`: Your [W&B authorization token](https://wandb.ai/authorize).


```python
import datetime
import json

import requests

# Headers and URLs
headers = {"Content-Type": "application/json"}
url_start = "https://trace.wandb.ai/call/start"
url_end = "https://trace.wandb.ai/call/end"
url_stream_query = "https://trace.wandb.ai/calls/stream_query"

# W&B variables
team_id = ""
project_id = ""
wandb_token = ""
```

## Simple trace
The following sections walk you through creating a simple trace.

1. [Start a simple trace](#start-a-simple-trace)
2. [End a simple trace](#end-a-simple-trace)

### Start a simple trace 

The following code creates a sample LLM call `payload_start` and logs it to Weave using the `url_start` endpoint. The `payload_start` object mimics a call to OpenAI's `gpt-4o` with the query `Why is the sky blue?`.

On success, this code will output a message indicating that the trace was started:

```
Call started. ID: 01939cdc-38d2-7d61-940d-dcca0a56c575, Trace ID: 01939cdc-38d2-7d61-940d-dcd0e76c5f34
```


```python
## ------------
## Start trace
## ------------
payload_start = {
    "start": {
        "project_id": f"{team_id}/{project_id}",
        "op_name": "simple_trace",
        "started_at": datetime.datetime.now().isoformat(),
        "inputs": {
            # Use this "messages" style to generate the chat UI in the expanded trace.
            "messages": [{"role": "user", "content": "Why is the sky blue?"}],
            "model": "gpt-4o",
        },
        "attributes": {},
    }
}
response = requests.post(
    url_start, headers=headers, json=payload_start, auth=("api", wandb_token)
)
if response.status_code == 200:
    data = response.json()
    call_id = data.get("id")
    trace_id = data.get("trace_id")
    print(f"Call started. ID: {call_id}, Trace ID: {trace_id}")
else:
    print("Start request failed with status:", response.status_code)
    print(response.text)
    exit()
```

### End a simple trace

To complete the simple trace, the following code creates a sample LLM call `payload_end` and logs it to Weave using the `url_end` endpoint. The `payload_end` object mimics the response from OpenAI's `gpt-4o` given the query `Why is the sky blue?`. The object is formatted so that pricing summary information and the chat completion are generated in trace view in the Weave Dashboard.

On success, this code will output a message indicating that the trace completed:

```
Call ended.
```


```python
## ------------
## End trace
## ------------
payload_end = {
    "end": {
        "project_id": f"{team_id}/{project_id}",
        "id": call_id,
        "ended_at": datetime.datetime.now().isoformat(),
        "output": {
            # Use this "choices" style to add the completion to the chat UI in the expanded trace.
            "choices": [
                {
                    "message": {
                        "content": "It’s due to Rayleigh scattering, where shorter blue wavelengths of sunlight scatter in all directions."
                    }
                },
            ]
        },
        # Format the summary like this to generate the pricing summary information in the traces table.
        "summary": {
            "usage": {
                "gpt-4o": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                    "requests": 1,
                }
            }
        },
    }
}
response = requests.post(
    url_end, headers=headers, json=payload_end, auth=("api", wandb_token)
)
if response.status_code == 200:
    print("Call ended.")
else:
    print("End request failed with status:", response.status_code)
    print(response.text)
```

## Complex trace
The following sections walk you through creating a more complex trace with child spans, similar to a mult-operation RAG lookup.

1. [Start a complex trace](#complex-trace)
2. [Add a child span: RAG document lookup](#add-a-child-span-to-a-complex-trace-rag-document-lookup)
3. [Add a child span: LLM completion call](#add-a-child-span-to-a-complex-trace-llm-completion-call)
4. [End a complex trace](#end-a-complex-trace)

### Start a complex trace 

The following code demonstrates how to create a more complex trace with multiple spans. An example of this would be a Retrieval-Augmented Generation (RAG) lookup followed by an LLM call. The first part initializes a parent trace(`payload_parent_start`) that represents the overall operation. In this case, the operation is  processing the user query `Can you summarize the key points of this document?`.

The `payload_parent_start` object mimics the initial step in a multi-step workflow, logging the the operation in Weave using the `url_start` endpoint.

On success, this code will output a message indicating that the parent call was logged:

```
Parent call started. ID: 01939d26-0844-7c43-94bb-cdc471b6d65f, Trace ID: 01939d26-0844-7c43-94bb-cdd97dc296c8
```


```python
## ------------
## Start trace (parent)
## ------------

# Parent call: Start
payload_parent_start = {
    "start": {
        "project_id": f"{team_id}/{project_id}",
        "op_name": "complex_trace",
        "started_at": datetime.datetime.now().isoformat(),
        "inputs": {"question": "Can you summarize the key points of this document?"},
        "attributes": {},
    }
}
response = requests.post(
    url_start, headers=headers, json=payload_parent_start, auth=("api", wandb_token)
)
if response.status_code == 200:
    data = response.json()
    parent_call_id = data.get("id")
    trace_id = data.get("trace_id")
    print(f"Parent call started. ID: {parent_call_id}, Trace ID: {trace_id}")
else:
    print("Parent start request failed with status:", response.status_code)
    print(response.text)
    exit()
```

### Add a child span to a complex trace: RAG document lookup

The following code demonstrates how to add a child span to the parent trace started in the previous step. This step models a the RAG document lookup sub-operation in the overarching workflow.

The child trace is initiated with the `payload_child_start` object, which includes:
- `trace_id`: Links this child span to the parent trace.
- `parent_id`: Associates the child span with the parent operation.
- `inputs`: Logs the search query, e.g., 
  `"This is a search query of the documents I'm looking for."`

On a successful call to the `url_start` endpoint, the code outputs a message indicating that the child call was started and completed:

```
Child call started. ID: 01939d32-23d6-75f2-9128-36a4a806f179
Child call ended.
```


```python
## ------------
## Child span:
## Ex. RAG Document lookup
## ------------

# Child call: Start
payload_child_start = {
    "start": {
        "project_id": f"{team_id}/{project_id}",
        "op_name": "rag_document_lookup",
        "trace_id": trace_id,
        "parent_id": parent_call_id,
        "started_at": datetime.datetime.now().isoformat(),
        "inputs": {
            "document_search": "This is a search query of the documents I'm looking for."
        },
        "attributes": {},
    }
}
response = requests.post(
    url_start, headers=headers, json=payload_child_start, auth=("api", wandb_token)
)
if response.status_code == 200:
    data = response.json()
    child_call_id = data.get("id")
    print(f"Child call started. ID: {child_call_id}")
else:
    print("Child start request failed with status:", response.status_code)
    print(response.text)
    exit()

# Child call: End
payload_child_end = {
    "end": {
        "project_id": f"{team_id}/{project_id}",
        "id": child_call_id,
        "ended_at": datetime.datetime.now().isoformat(),
        "output": {
            "document_results": "This will be the RAG'd document text which will be returned from the search query."
        },
        "summary": {},
    }
}
response = requests.post(
    url_end, headers=headers, json=payload_child_end, auth=("api", wandb_token)
)
if response.status_code == 200:
    print("Child call ended.")
else:
    print("Child end request failed with status:", response.status_code)
    print(response.text)
```

### Add a child span to a complex trace: LLM completion call

The following code demonstrates how to add another child span to the parent trace, representing an LLM completion call. This step models the AI's response generation based on document context retrieved in the previous RAG operation.

The LLM completion trace is initiated with the `payload_child_start` object, which includes:
- `trace_id`: Links this child span to the parent trace.
- `parent_id`: Associates the child span with the overarching workflow.
- `inputs`: Logs the input messages for the LLM, including the user query and the appended document context.
- `model`: Specifies the model used for the operation (`gpt-4o`).

On success, the code outputs a message indicating the LLM child span trace has started and ended:

```
Child call started. ID: 0245acdf-83a9-4c90-90df-dcb2b89f234a
```

Once the operation completes, the `payload_child_end` object ends the trace by logging the LLM-generated response in the `output` field. Usage summary information is also logged.

On success, the code outputs a message indicating the LLM child span trace has started and ended:

```
Child call started. ID: 0245acdf-83a9-4c90-90df-dcb2b89f234a
Child call ended.
```


```python
## ------------
## Child span:
## Create an LLM completion call
## ------------

# Child call: Start
payload_child_start = {
    "start": {
        "project_id": f"{team_id}/{project_id}",
        "op_name": "llm_completion",
        "trace_id": trace_id,
        "parent_id": parent_call_id,
        "started_at": datetime.datetime.now().isoformat(),
        "inputs": {
            "messages": [
                {
                    "role": "user",
                    "content": "With the following document context, could you help me answer:\n Can you summarize the key points of this document?\n [+ appended document context]",
                }
            ],
            "model": "gpt-4o",
        },
        "attributes": {},
    }
}
response = requests.post(
    url_start, headers=headers, json=payload_child_start, auth=("api", wandb_token)
)
if response.status_code == 200:
    data = response.json()
    child_call_id = data.get("id")
    print(f"Child call started. ID: {child_call_id}")
else:
    print("Child start request failed with status:", response.status_code)
    print(response.text)
    exit()

# Child call: End
payload_child_end = {
    "end": {
        "project_id": f"{team_id}/{project_id}",
        "id": child_call_id,
        "ended_at": datetime.datetime.now().isoformat(),
        "output": {
            "choices": [
                {"message": {"content": "This is the response generated by the LLM."}},
            ]
        },
        "summary": {
            "usage": {
                "gpt-4o": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                    "requests": 1,
                }
            }
        },
    }
}
response = requests.post(
    url_end, headers=headers, json=payload_child_end, auth=("api", wandb_token)
)
if response.status_code == 200:
    print("Child call ended.")
else:
    print("Child end request failed with status:", response.status_code)
    print(response.text)
```

### End a complex trace

The following code demonstrates how to finalize the parent trace, marking the completion of the entire workflow. This step aggregates the results of all child spans (e.g., RAG lookup and LLM completion) and logs the final output and metadata.

The trace is finalized using the `payload_parent_end` object, which includes:
- `id`: The `parent_call_id` from the initial parent trace start.
- `output`: Represents the final output of the entire workflow. 
- `summary`: Consolidates usage data for the entire workflow.
- `prompt_tokens`: Total tokens used for all prompts.
- `completion_tokens`: Total tokens generated in all responses.
- `total_tokens`: Combined token count for the workflow.
- `requests`: Total number of requests made (in this case, `1`).

On success, the code outputs:

```
Parent call ended.
```


```python
## ------------
## End trace
## ------------

# Parent call: End
payload_parent_end = {
    "end": {
        "project_id": f"{team_id}/{project_id}",
        "id": parent_call_id,
        "ended_at": datetime.datetime.now().isoformat(),
        "output": {
            "choices": [
                {"message": {"content": "This is the response generated by the LLM."}},
            ]
        },
        "summary": {
            "usage": {
                "gpt-4o": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                    "requests": 1,
                }
            }
        },
    }
}
response = requests.post(
    url_end, headers=headers, json=payload_parent_end, auth=("api", wandb_token)
)
if response.status_code == 200:
    print("Parent call ended.")
else:
    print("Parent end request failed with status:", response.status_code)
    print(response.text)
```

## Run a lookup query
The following code demonstrates how to query the traces created in previous examples, filtering only for traces where the `inputs.model` field is equal to `gpt-4o`.

The `query_payload` object includes:
- `project_id`: Identifies the team and project to query.
- `filter`: Ensures the query returns only **trace roots** (top-level traces).
- `query`: Defines the filter logic using the `$expr` operator:
  - `$getField`: Retrieves the `inputs.model` field.
  - `$literal`: Matches traces where `inputs.model` equals `"gpt-4o"`.
- `limit`: Limits the query to 10,000 results.
- `offset`: Starts the query at the first result.
- `sort_by`: Orders results by the `started_at` timestamp in descending order.
- `include_feedback`: Excludes feedback data from the results.

On a successful query, the response will include trace data matching the query parameters:

```
{'id': '01939cf3-541f-76d3-ade3-50cfae068b39', 'project_id': 'cool-new-team/uncategorized', 'op_name': 'simple_trace', 'display_name': None, 'trace_id': '01939cf3-541f-76d3-ade3-50d5cfabe2db', 'parent_id': None, 'started_at': '2024-12-06T17:10:12.590000Z', 'attributes': {}, 'inputs': {'messages': [{'role': 'user', 'content': 'Why is the sky blue?'}], 'model': 'gpt-4o'}, 'ended_at': '2024-12-06T17:47:08.553000Z', 'exception': None, 'output': {'choices': [{'message': {'content': 'It’s due to Rayleigh scattering, where shorter blue wavelengths of sunlight scatter in all directions.'}}]}, 'summary': {'usage': {'gpt-4o': {'prompt_tokens': 10, 'completion_tokens': 20, 'requests': 1, 'total_tokens': 30}}, 'weave': {'status': 'success', 'trace_name': 'simple_trace', 'latency_ms': 2215963}}, 'wb_user_id': 'VXNlcjoyMDk5Njc0', 'wb_run_id': None, 'deleted_at': None}
```





```python
query_payload = {
    "project_id": f"{team_id}/{project_id}",
    "filter": {"trace_roots_only": True},
    "query": {
        "$expr": {"$eq": [{"$getField": "inputs.model"}, {"$literal": "gpt-4o"}]}
    },
    "limit": 10000,
    "offset": 0,
    "sort_by": [{"field": "started_at", "direction": "desc"}],
    "include_feedback": False,
}
response = requests.post(
    url_stream_query, headers=headers, json=query_payload, auth=("api", wandb_token)
)
if response.status_code == 200:
    print("Query successful!")
    try:
        data = response.json()
        print(data)
    except json.JSONDecodeError as e:
        # Alternate decode
        json_objects = response.text.strip().split("\n")
        parsed_data = [json.loads(obj) for obj in json_objects]
        print(parsed_data)
else:
    print(f"Query failed with status code: {response.status_code}")
    print(response.text)
```
