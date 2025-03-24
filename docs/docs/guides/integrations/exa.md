# Exa

Weave automatically tracks and logs search calls made via the [Exa Python library](https://github.com/exaai/exa-py), allowing you to monitor costs and usage.

## Traces

It's important to store traces of search API calls in a central database, both during development and in production. You'll use these traces for debugging, cost analysis, and to help improve your application.

Weave will automatically capture traces for [exa-py](https://github.com/exaai/exa-py). You can use the library as usual, start by calling `weave.init()`:

```python
import os
from exa_py import Exa
import weave

weave.init("web_research")

# Initialize Exa
exa = Exa(os.getenv('EXA_API_KEY'))

# Make your Exa query
result = exa.search(
    "Latest developments in quantum computing",
)

print(result)
```

Weave will now track and log all API calls made through the Exa library, including cost information. You can view the traces in the Weave web interface.

## Wrapping with your own ops

Weave ops make results *reproducible* by automatically versioning code as you experiment, and they capture their inputs and outputs. Simply create a function decorated with [`@weave.op()`](/guides/tracking/ops) that calls into Exa and Weave will track the inputs, outputs, and costs for you:

```python
@weave.op
def research_topic(query: str, result_type: str = "auto") -> dict:
    "Search for information on a specific topic"
    
    # Initialize Exa
    exa = Exa(os.getenv('EXA_API_KEY'))
    
    # Perform the search
    results = exa.search_and_contents(
        query,
        text=True,
    )
    
    return results

# Try different searches
research_topic("Recent breakthroughs in renewable energy")
research_topic("Current state of quantum computing")
research_topic("Advancements in autonomous vehicles")
```

## Create a `Model` for easier experimentation

Organizing experimentation is difficult when there are many moving pieces. By using the [`Model`](/guides/core-types/models) class, you can capture and organize the experimental details of your research app, like search parameters or result types.

In the example below, you can experiment with different search configurations. Every time you change one of these, you'll get a new _version_ of `ResearchAssistant`.

```python
import os
import weave
from exa_py import Exa

weave.init("web_research_project")

class ResearchAssistant(weave.Model):
    max_results: int

    @weave.op
    def predict(self, query: str) -> dict:
        "Search for information on a specific topic"
        
        # Initialize Exa
        exa = Exa(os.getenv('EXA_API_KEY'))
        
        # Perform the search
        results = exa.search_and_contents(
            query,
            text=True,
            type="auto",
            num_results=self.max_results,
        )
        
        return results

# Create and use a research model
research_model = ResearchAssistant(
    max_results=5
)

result = research_model.predict(query="Latest developments in AI safety")
print(result)
```

## Cost Tracking

Weave automatically captures cost information from Exa API calls, allowing you to monitor your usage and expenses. This cost data is integrated with Weave's usage tracking system, making it easy to analyze and manage your spending.