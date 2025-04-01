# Tutorial: Build a Class-Based Scorer using the Vale Linter

Weave scorers let you evaluate the quality of LLM outputs across many dimensions — relevance, factuality, style, etc. But out of the box, most existing scorers are designed for semantic correctness or task accuracy, not writing style.

In this tutorial, you'll build a custom `Scorer` class that uses [Vale](https://vale.sh) — a popular open-source documentation linter — to score **style and grammar quality** in LLM-generated writing.

This is particularly useful for:
- Evaluating chatbot or assistant outputs against a company style guide
- Measuring adherence to documentation standards (Google, Microsoft, etc.)
- Scoring doc rewrites, auto-suggested PRs, or content snippets

:::Why Vale?  
Vale lets you codify editorial style guides — things like "use active voice", "avoid future tense", "Oxford comma required" — and automatically flags violations. It’s widely used in tech writing, and makes a perfect complement to LLM scoring.
:::

## Prerequisites

Before you begin, install:

- [Weave](https://pypi.org/project/weave/)
- [Vale linter](https://vale.sh/docs/install)
- Python 3.8+


## Configure Vale

To get useful linting feedback, you'll need a Vale configuration file and at least one [Vale style package installed](https://vale.sh/explorer).

1. Create a [`.vale.ini`](https://vale.sh/docs/vale-ini) file in your repo root. The following example shows a `.vale.ini` that configures Vale to output all levels of style violation (`error`, `warning`, and `suggestion`) and lint docs against the [`Google`](https://github.com/errata-ai/Google) and [`write-good`](https://github.com/errata-ai/write-good) style guides.

    ```ini
    StylesPath = styles
    MinAlertLevel = suggestion

    [*.md]
    BasedOnStyles = Google, WriteGood
    ```

This tells Vale to use styles located in a local `styles/` folder and apply them to `.md` files.

2. To initialize Vale with the configuration, use the Vale `sync` command.

   ```bash
   vale sync
   ```

   You can also create [custom Vale style rules](https://vale.sh/docs/styles) to enforce your product name, brand capitalization, or terminology usage.

## Define the `ValeScorer` class

We’ll now define a custom Scorer class that runs Vale on text content and returns lint results in a Weave-friendly format. Like all class-based scorers, `ValeScorer` inherits from `weave.Scorer`.

The .score() method is decorated with @weave.op so every evaluation is traceable in Weave

The input string is written to a temporary .md file

The Vale CLI tool is ran as a subprocess

`ValeScorer` returns:

- Pass/fail
- Number of style issues
- Issue breakdown by severity
- Full issue list

```python
import tempfile
import subprocess
import json
import weave
from weave import Scorer

class ValeScorer(Scorer):
    """
    A Scorer that runs Vale on markdown strings and returns style violations.
    """

    vale_path: str = "vale"  # Adjust if Vale is not on your PATH

    @weave.op
    def score(self, output: str) -> dict:
        # Write the content to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w+", delete=False) as tmp_file:
            tmp_file.write(output)
            tmp_file.flush()
            tmp_file_name = tmp_file.name

        try:
            result = subprocess.run(
                [self.vale_path, "--output=JSON", tmp_file_name],
                capture_output=True,
                text=True,
                check=False,
            )
            issues = json.loads(result.stdout).get(tmp_file_name, [])
        except Exception as e:
            return {
                "passed": False,
                "error": f"Vale invocation failed: {str(e)}",
                "issues": [],
            }

        severity_counts = {}
        for issue in issues:
            sev = issue.get("Severity", "suggestion").lower()
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            "passed": len(issues) == 0,
            "issue_count": len(issues),
            "severity_breakdown": severity_counts,
            "issues": issues,
        }
```


## Run a test evaluation

Now that you have a scorer, you can run an evaluation. To do so, create a `Dataset` with content examples that violate style rules that you are scoring ("use active voice", "avoid future tense", "Oxford comma required", etc.) and a model to evaluate.

In the following example, the test dataset simply includes two markdown examples that violate common style rules, and the `echo_model` just returns the input text (useful for testing scorers in isolation). All results are logged to the Weave `vale-scorer-demo` project.

```python
from weave import Evaluation
import asyncio

examples = [
    {"content": "We will now show how to run the code."},
    {"content": "This thing maybe will be possibly unclear."}
]

# Simple model that returns the input text (for demonstration)
@weave.op()
def echo_model(content: str) -> dict:
    return {"content": content}

# Instantiate your ValeScorer
scorer = ValeScorer()

# Run the evaluation
weave.init("vale-scorer-demo")
evaluation = Evaluation(dataset=examples, scorers=[scorer])
asyncio.run(evaluation.evaluate(echo_model))
```

## View results in Weave