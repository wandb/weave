---
title: Integrating with Weave - Production Dashboard
---


:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/online_monitoring.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/online_monitoring.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::



<!--- @wandbcode{cod-notebook} -->


# Integrating with Weave: Production Dashboard

The GenAI tooling landscape is rapidly evolving - new frameworks, tools, and applications are emerging all the time. Weave aims to be a one-stop-shop for all your GenAI monitoring and evaluation needs. This also means that sometimes it is necessary to integrate with existing platforms or extend Weave to fit the specific needs of your project or organization.

In this cookbook, we'll demonstrate how to leverage Weave's powerful APIs and functions to create a custom dashboard for production monitoring as an extension to the Traces view in Weave. We'll focus on:

- Fetching traces, costs, feedback, and other metrics from Weave
- Creating aggregate views for user feedback and cost distribution
- Creating visualizations for token usage and latency over time

You can try out the dashboard with your own Weave project by installing streamlit and running [this production dashboard script](https://github.com/NiWaRe/agent-dev-collection)!


<img src="https://github.com/NiWaRe/knowledge-worker-weave/blob/master/screenshots/dashboard_weave_preview.jpg?raw=true" width="1000" alt="Example Production Dashboard with Weave" />


# 1. Setup

To follow along this tutorial you'll only need to install the following packages:



```python
!pip install streamlit pandas plotly weave
```

# 2. Implementation


## 2.1 Initializing Weave Client and Defining Costs

First, we'll set up a function to initialize the Weave client and add costs for each model.

- We have included the standard costs for many standard models but we also make it easy to add your own custom costs and custom models. In the following we'll show how to add custom costs for a few models and use the standard costs for the rest.
- The costs are calculate based on the tracked tokens for each call in Weave. For many LLM vendor libraries, we will automatically track the token usage, but it is also possible to return custom token counts for any call. See this cookbook on how to define the token count and cost calculation for a custom model - [custom cost cookbook](https://weave-docs.wandb.ai/reference/gen_notebooks/custom_model_cost#setting-up-a-model-with-weave).



```python
PROJECT_NAME = "wandb-smle/weave-cookboook-demo"
```


```python
import weave

MODEL_NAMES = [
    # model name, prompt cost, completion cost
    ("gpt-4o-2024-05-13", 0.03, 0.06),
    ("gpt-4o-mini-2024-07-18", 0.03, 0.06),
    ("gemini/gemini-1.5-flash", 0.00025, 0.0005),
    ("gpt-4o-mini", 0.03, 0.06),
    ("gpt-4-turbo", 0.03, 0.06),
    ("claude-3-haiku-20240307", 0.01, 0.03),
    ("gpt-4o", 0.03, 0.06),
]


def init_weave_client(project_name):
    try:
        client = weave.init(project_name)
        for model, prompt_cost, completion_cost in MODEL_NAMES:
            client.add_cost(
                llm_id=model,
                prompt_token_cost=prompt_cost,
                completion_token_cost=completion_cost,
            )
    except Exception as e:
        print(f"Failed to initialize Weave client for project '{project_name}': {e}")
        return None
    else:
        return client


client = init_weave_client(PROJECT_NAME)
```

## 2.2 Fetching Calls Data from Weave

In order to fetch call data from Weave, we have two options:

1. Fetching Data call-by-call
2. Using high-level APIs

### 2.2.1 Fetching Data call-by-call

The first option to access data from Weave is to retrieve a list of filtered calls and extract the wanted data call-by-call. For that we can use the `calls_query_stream` API to fetch the calls data from Weave:

- `calls_query_stream` API: This API allows us to fetch the calls data from Weave.
- `filter` dictionary: This dictionary contains the filter parameters to fetch the calls data - see [here](https://weave-docs.wandb.ai/reference/python-sdk/weave/trace_server/weave.trace_server.trace_server_interface/#class-callschema) for more details.
- `expand_columns` list: This list contains the columns to expand in the calls data.
- `sort_by` list: This list contains the sorting parameters for the calls data.
- `include_costs` boolean: This boolean indicates whether to include the costs in the calls data.
- `include_feedback` boolean: This boolean indicates whether to include the feedback in the calls data.



```python
import itertools
from datetime import datetime, timedelta

import pandas as pd


def fetch_calls(client, project_id, start_time, trace_roots_only, limit):
    filter_params = {
        "project_id": project_id,
        "filter": {"started_at": start_time, "trace_roots_only": trace_roots_only},
        "expand_columns": ["inputs.example", "inputs.model"],
        "sort_by": [{"field": "started_at", "direction": "desc"}],
        "include_costs": True,
        "include_feedback": True,
    }
    try:
        calls_stream = client.server.calls_query_stream(filter_params)
        calls = list(
            itertools.islice(calls_stream, limit)
        )  # limit the number of calls to fetch if too many
        print(f"Fetched {len(calls)} calls.")
    except Exception as e:
        print(f"Error fetching calls: {e}")
        return []
    else:
        return calls


calls = fetch_calls(client, PROJECT_NAME, datetime.now() - timedelta(days=1), True, 100)
```


```python
# the raw data is a list of Call objects
pd.DataFrame([call.dict() for call in calls]).head(3)
```

Processing the calls is very easy with the return from Weave - we'll extract the relevant information and store it in a list of dictionaries. We'll then convert the list of dictionaries to a pandas DataFrame and return it.



```python
import json
from datetime import datetime

import pandas as pd


def process_calls(calls):
    records = []
    for call in calls:
        feedback = call.summary.get("weave", {}).get("feedback", [])
        thumbs_up = sum(
            1
            for item in feedback
            if isinstance(item, dict) and item.get("payload", {}).get("emoji") == "👍"
        )
        thumbs_down = sum(
            1
            for item in feedback
            if isinstance(item, dict) and item.get("payload", {}).get("emoji") == "👎"
        )
        latency = call.summary.get("weave", {}).get("latency_ms", 0)

        records.append(
            {
                "Call ID": call.id,
                "Trace ID": call.trace_id,  # this is a unique ID for the trace that can be used to retrieve it
                "Display Name": call.display_name,  # this is an optional name you can set in the UI or programatically
                "Latency (ms)": latency,
                "Thumbs Up": thumbs_up,
                "Thumbs Down": thumbs_down,
                "Started At": pd.to_datetime(getattr(call, "started_at", datetime.min)),
                "Inputs": json.dumps(call.inputs, default=str),
                "Outputs": json.dumps(call.output, default=str),
            }
        )
    return pd.DataFrame(records)
```


```python
df_calls = process_calls(calls)
df_calls.head(3)
```

### 2.2.2 Using high-level APIs

Instead of goin through every call Weave also provides high-level APIs to directly access model costs, feedback, and other metrics.
For example, for the cost, we'll use the `query_costs` API to fetch the costs of all used LLMs using in project:



```python
# Use cost API to get costs
costs = client.query_costs()
df_costs = pd.DataFrame([cost.dict() for cost in costs])
df_costs["total_cost"] = (
    df_costs["prompt_token_cost"] + df_costs["completion_token_cost"]
)

# only show the first row for every unqiue llm_id
df_costs
```

## 2.4 Gathering inputs and generating visualizations

Next, we can generate the visualizations using plotly. This is the most basic dashboard, but you can customize it as you like! For a more complex example, check out a Streamlit example [here](https://github.com/NiWaRe/knowledge-worker-weave/blob/master/prod_dashboard.py).



```python
import plotly.express as px
import plotly.graph_objects as go


def plot_feedback_pie_chart(thumbs_up, thumbs_down):
    fig = go.Figure(
        data=[
            go.Pie(
                labels=["Thumbs Up", "Thumbs Down"],
                values=[thumbs_up, thumbs_down],
                marker={"colors": ["#66b3ff", "#ff9999"]},
                hole=0.3,
            )
        ]
    )
    fig.update_traces(textinfo="percent+label", hoverinfo="label+percent")
    fig.update_layout(showlegend=False, title="Feedback Summary")
    return fig


def plot_model_cost_distribution(df):
    fig = px.bar(
        df,
        x="llm_id",
        y="total_cost",
        color="llm_id",
        title="Cost Distribution by Model",
    )
    fig.update_layout(xaxis_title="Model", yaxis_title="Cost (USD)")
    return fig


# See the source code for all the plots
```


```python
plot_feedback_pie_chart(df_calls["Thumbs Up"].sum(), df_calls["Thumbs Down"].sum())
```


```python
plot_model_cost_distribution(df_costs)
```

# Conclusion

In this cookbook, we demonstrated how to create a custom production monitoring dashboard using Weave's APIs and functions. Weave currently focuses on fast integrations for easy input of data as well as extraction of the data for custom processes.

- **Data Input:**
  - Framework-agnostic tracing with [@weave-op()](https://weave-docs.wandb.ai/quickstart#2-log-a-trace-to-a-new-project) decorator and the possibility to import calls from CSV (see related [import cookbook](https://weave-docs.wandb.ai/reference/gen_notebooks/import_from_csv))
  - Service API endpoints to log to Weave from for various programming frameworks and languages, see [here](https://weave-docs.wandb.ai/reference/service-api/call-start-call-start-post) for more details.
- **Data Output:**
  - Easy download of the data in CSV, TSV, JSONL, JSON formats - see [here](https://weave-docs.wandb.ai/guides/tracking/tracing#querying--exporting-calls) for more details.
  - Easy export using programmatic access to the data - see "Use Python" section in the export panel as described in this cookbook. See [here](https://weave-docs.wandb.ai/guides/tracking/tracing#querying--exporting-calls) for more details.

This custom dashboard extends Weave's native Traces view, allowing for tailored monitoring of LLM applications in production. If you're interested in viewing a more complex dashboard, check out a Streamlit example where you can add your own Weave project URL [in this repo](https://github.com/NiWaRe/agent-dev-collection).

