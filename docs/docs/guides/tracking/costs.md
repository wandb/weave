import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Costs

## Adding a custom cost

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    You can add a custom cost by using the [`add_cost`](/reference/python-sdk/weave/trace/weave.trace.weave_client#method-add_cost) method.
    The three required fields are `llm_id`, `prompt_token_cost`, and `completion_token_cost`.
    `llm_id` is the name of the LLM (e.g. `gpt-4o`). `prompt_token_cost` and `completion_token_cost` are cost per token for the LLM (if the LLM prices were specified inper million tokens, make sure to convert the value).
    You can also set `effective_date` to a datetime, to make the cost effective at a specific date, this defaults to the current date.

    ```python
    import weave
    from datetime import datetime

    client = weave.init("my_custom_cost_model")

    client.add_cost(
        llm_id="your_model_name",
        prompt_token_cost=0.01,
        completion_token_cost=0.02
    )

    client.add_costs(
        llm_id="your_model_name",
        prompt_token_cost=10,
        completion_token_cost=20,
        # If for example I want to raise the price of the model after a certain date
        effective_date=datetime(2025, 4, 22),
    )
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">

    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```

  </TabItem>
</Tabs>

## Querying for costs

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    You can query for costs by using the [`query_costs`](/reference/python-sdk/weave/trace/weave.trace.weave_client#method-query_costs) method.
    There are a few ways to query for costs, you can pass in a singular cost id, or a list of LLM model names.

    ```python
    import weave

    client = weave.init("my_custom_cost_model")

    costs = client.query_costs(llm_ids=["your_model_name"])

    cost = client.query_costs(costs[0].id)
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">

    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```

  </TabItem>
</Tabs>

## Purging a custom cost

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    You can purge a custom cost by using the [`purge_costs`](/reference/python-sdk/weave/trace/weave.trace.weave_client#method-purge_costs) method. You pass in a list of cost ids, and the costs with those ids are purged.

    ```python
    import weave

    client = weave.init("my_custom_cost_model")

    costs = client.query_costs(llm_ids=["your_model_name"])
    client.purge_costs([cost.id for cost in costs])
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

## Calculating costs for a Project

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    You can calculate costs for a project by using our `calls_query` and adding `include_costs=True` with a little bit of setup.

    ```python
    import weave

    weave.init("project_costs")
    @weave.op()
    def get_costs_for_project(project_name: str):
        total_cost = 0
        requests = 0

        client = weave.init(project_name)
        # Fetch all the calls in the project
        calls = list(
            client.get_calls(filter={"trace_roots_only": True}, include_costs=True)
        )

        for call in calls:
            # If the call has costs, we add them to the total cost
            if call.summary["weave"] is not None and call.summary["weave"].get("costs", None) is not None:
                for k, cost in call.summary["weave"]["costs"].items():
                    requests += cost["requests"]
                    total_cost += cost["prompt_tokens_total_cost"]
                    total_cost += cost["completion_tokens_total_cost"]

        # We return the total cost, requests, and calls
        return {
            "total_cost": total_cost,
            "requests": requests,
            "calls": len(calls),
        }

    # Since we decorated our function with @weave.op(),
    # our totals are stored in weave for historic cost total calculations
    get_costs_for_project("my_custom_cost_model")
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

## Setting up a custom model with custom costs

Try our cookbook for a [Setting up costs with a custom model](/reference/gen_notebooks/custom_model_cost) or <a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/custom_model_cost.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>
