---
title: Integrating with Weave - Production Dashboard
---


:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/dashboard_integraion.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/dashboard_integraion.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::



<img src="http://wandb.me/logo-im-png" width="400" alt="Weights & Biases" />
<!--- @wandbcode{cod-notebook} -->

# Integrating with Weave: Production Dashboard

The GenAI tooling landscape is rapidly evolving - new frameworks, tools, and applications are emerging all the time. Weave aims to be a one-stop-shop for all your GenAI monitoring and evaluation needs. This also means that sometimes it is necessary to integrate with existing platforms or extend Weave to fit the personal needs of the specific company.

In this cookbook, we'll demonstrate how to leverage Weave's powerful APIs and functions to create a custom dashboard for production monitoring as an extension to the Traces view in Weave. We'll focus on:
* Fetching data from Weave
* Creating aggregate views for user feedback and cost distribution
* Creating visualizations for token usage and latency over time

You can try out the dashboard with your own Weave project by installing streamlit and running [this script](https://github.com/NiWaRe/knowledge-worker-weave/blob/master/prod_dashboard.py)!

<img src="https://github.com/NiWaRe/knowledge-worker-weave/blob/master/screenshots/dashboard_weave_preview.jpg?raw=true" width="1000" alt="Example Production Dashboard with Weave" />

# 1. Setup
To follow along this tutorial you'll only need to install the following packages:


```python
!pip install streamlit pandas plotly weave
```

# 2. Implementation

## 2.1 Initializing Weave Client and Defining Costs
First, we'll set up a function to initialize the Weave client and add costs for each model. These costs are used to calculate the total cost of each call in Weave based on the tracked tokens during inference. We can also add an `effective_date` parameter to the function to set the date when the costs should be effective - more information about the `add_cost` function [here](https://weave-docs.wandb.ai/guides/tracking/costs).


```python
import weave
import streamlit as st

MODEL_NAMES = [
    # model name, prompt cost, completion cost
    ("gpt-4o-2024-05-13", 0.03, 0.06),
    ("gpt-4o-mini-2024-07-18", 0.03, 0.06),
    ("gemini/gemini-1.5-flash", 0.00025, 0.0005),
    ("gpt-4o-mini", 0.03, 0.06),
    ("gpt-4-turbo", 0.03, 0.06),
    ("claude-3-haiku-20240307", 0.01, 0.03),
    ("gpt-4o", 0.03, 0.06)
]

@st.cache_resource
def init_weave_client(project_name):
    try:
        client = weave.init(project_name)
        for model, prompt_cost, completion_cost in MODEL_NAMES:
            client.add_cost(llm_id=model, prompt_token_cost=prompt_cost, completion_token_cost=completion_cost)
        return client
    except Exception as e:
        st.error(f"Failed to initialize Weave client for project '{project_name}': {e}")
        return None
```

## 2.2 Fetching Calls Data from Weave
Next, we'll use the `calls_query_stream` API to fetch the calls data from Weave:

* `calls_query_stream` API: This API allows us to fetch the calls data from Weave.
* `filter` dictionary: This dictionary contains the filter parameters to fetch the calls data - see [here](https://weave-docs.wandb.ai/reference/python-sdk/weave/trace_server/weave.trace_server.trace_server_interface/#class-callschema) for more details.
* `expand_columns` list: This list contains the columns to expand in the calls data.
* `sort_by` list: This list contains the sorting parameters for the calls data.
* `include_costs` boolean: This boolean indicates whether to include the costs in the calls data.
* `include_feedback` boolean: This boolean indicates whether to include the feedback in the calls data.


```python
import itertools

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
        calls = list(itertools.islice(calls_stream, limit)) # limit the number of calls to fetch if too many
        st.write(f"Fetched {len(calls)} calls.")
        return calls
    except Exception as e:
        st.error(f"Error fetching calls: {e}")
        return []
```

For the cost, we'll use the `query_costs` API to fetch the costs of all used LLMs using a single call from Weave:


```python
# Use cost API to get costs
client = init_weave_client(selected_project)
if client is None:
    st.stop()

costs = client.query_costs()
df_costs = pd.DataFrame([cost.dict() for cost in costs])
df_costs['total_cost'] = df_costs['prompt_token_cost'] + df_costs['completion_token_cost']
```

## 2.3 Processing Calls Data
Processing the calls is very easy with the return from Weave - we'll extract the relevant information and store it in a list of dictionaries. We'll then convert the list of dictionaries to a pandas DataFrame and return it.


```python
import json
import pandas as pd
from datetime import datetime, timedelta

def process_calls(calls):
    records = []
    for call in calls:
        # For the latency and tokens we'll actually go through each call and extract model name from the inputs or outputs (this will change in the future)
        model = next((model for model, _, _ in MODEL_NAMES if model in json.dumps(call.inputs) or model in json.dumps(call.output)), "N/A")
        costs = call.summary.get("weave", {}).get("costs", {})
        total_tokens = sum(cost.get("prompt_tokens", 0) + cost.get("completion_tokens", 0) for cost in costs.values())
        feedback = call.summary.get("weave", {}).get("feedback", [])
        thumbs_up = sum(1 for item in feedback if isinstance(item, dict) and item.get("payload", {}).get("emoji") == "👍")
        thumbs_down = sum(1 for item in feedback if isinstance(item, dict) and item.get("payload", {}).get("emoji") == "👎")
        
        records.append({
            "Call ID": call.id,
            "Trace ID": call.trace_id,
            "Display Name": call.display_name,
            "Model": model,
            "Tokens": total_tokens,
            "Latency (ms)": call.summary.get("weave", {}).get("latency_ms", 0),
            "Thumbs Up": thumbs_up,
            "Thumbs Down": thumbs_down,
            "Started At": pd.to_datetime(getattr(call, 'started_at', datetime.min)),
            "Inputs": json.dumps(call.inputs, default=str),
            "Outputs": json.dumps(call.output, default=str)
        })
    return pd.DataFrame(records)
```

## 2.4 Gathering inputs and generating visualizations
Next, we'll gather the inputs using streamlit and generate the visualizations using plotly. This is the most basic dashboard, but you can customize it as you like! Check out the complete source code [here](https://github.com/NiWaRe/knowledge-worker-weave/blob/master/prod_dashboard.py).


```python
import plotly.express as px
import plotly.graph_objects as go

def plot_feedback_pie_chart(thumbs_up, thumbs_down):
    fig = go.Figure(data=[go.Pie(labels=['Thumbs Up', 'Thumbs Down'], values=[thumbs_up, thumbs_down], marker=dict(colors=['#66b3ff', '#ff9999']), hole=.3)])
    fig.update_traces(textinfo='percent+label', hoverinfo='label+percent')
    fig.update_layout(showlegend=False, title="Feedback Summary")
    return fig

def plot_model_cost_distribution(df):
    fig = px.bar(df, x="llm_id", y="total_cost", color="llm_id", title="Cost Distribution by Model")
    fig.update_layout(xaxis_title="Model", yaxis_title="Cost (USD)")
    return fig

# See the source code for all the plots
```


```python
AVAILABLE_PROJECTS = [
    # entity name, project name
    "wandb-smle/weave-cookboook-demo",
]

def render_dashboard():
    # Configs panel
    st.markdown("<div class='header'>Weave LLM Monitoring Dashboard</div>", unsafe_allow_html=True)

    trace_roots_only = st.sidebar.toggle("Trace Roots Only", value=True)
    selected_project = st.sidebar.selectbox("Select Weave Project", AVAILABLE_PROJECTS, index=0)
    client = init_weave_client(selected_project)
    if client is None:
        st.stop()

    # [...]: Check the source code for the rest of the dashboard

    # First plots - feedback and cost distribution
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(plot_feedback_pie_chart(thumbs_up, thumbs_down), use_container_width=True)
    with col2:
        st.plotly_chart(plot_model_cost_distribution(df_costs), use_container_width=True)
```

# Conclusion
In this cookbook, we demonstrated how to create a custom production monitoring dashboard using Weave's APIs and functions. Weave currently focuses on fast integrations for easy input of data as well as extraction of the data for custom processes.

* **Data Input:** 
    * Framework-agnostic tracing with [@weave-op()](https://weave-docs.wandb.ai/quickstart#2-log-a-trace-to-a-new-project) decorator and the possibility to import calls from CSV (see related [import cookbook](https://weave-docs.wandb.ai/reference/gen_notebooks/import_from_csv))
    * Service API endpoints to log to Weave from for various programming frameworks and languages, see [here](https://weave-docs.wandb.ai/reference/service-api/call-start-call-start-post) for more details.
* **Data Output:**
    * Easy download of the data in CSV, TSV, JSONL, JSON formats - see [here](https://weave-docs.wandb.ai/guides/tracking/tracing#querying--exporting-calls) for more details.
    * Easy export using programmatic access to the data - see "Use Python" section in the export panel as described in this cookbook. See [here](https://weave-docs.wandb.ai/guides/tracking/tracing#querying--exporting-calls) for more details.

This custom dashboard extends Weave's native Traces view, allowing for tailored monitoring of LLM applications in production. While this dashboard will soon be directly integrated into Weave, the easy programmatic data access will be preserved. This ensures that enterprises can continue to integrate Weave data into their existing monitoring tools and FinOps processes.
