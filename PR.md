# Eval APIs / Data Model V2

Our Evaluation Framework has served us well so far in allow us to experiement, iterate, and learn about the different use cases.
However, the current APIs and Data Model prevent us from generally supporting the use cases that we've identified.
This PR aims to address these problems, laying the groundwork for the next evolution of our evaluation framework.

Note 1: for ease of reading, I will use the term "evaluation framework" to refer to the pairing of APIs and Data Model when it is not important to distinguish between the two.
Note 2: There is a subtle distinction between the concept of an Evaluation and an Evaluation Run. However, we often use these terms interchangeably throughout the codebase. In this description, I will use "Evaluation" to refer to the definition of an Evaluation, and "EvaluationRun" to refer to the result of producing results for a Model against a given Evaluation.

## Current Data Model

The current logical data model consists of:
    * `Evaluation` - a Weave Evaluation that defines an Evaluation. It contains:
        * `Dataset` - a Weave Dataset that contains the data for the Eval (currently columns are completely user defined)
        * `Scorer`s - a list of Weave Scorer Objects (or Weave Ops) that are used to score the model against the data
            * Note: The user can define a custom scorer if they want to define custom aggregation logic, else an op is fine.
            * Note 2: The scorer function parameters must be (model_output, **some_subset_of_dataset_columns)
    * `EvaluationRun` - a Weave Call of the `Evaluation.evaluate` method op. It is paramterized by:
        * `Model` - a Weave Model (or Weave Op) that is used to make predictions. The parameters of the op must be a subset of the columns of the dataset.
        * `Trials` - the number of trails to run per-row of the dataset - this is critical in LLM evaluation due to inherent randomness - analysis must be able to aggregate across multiple trials.

Under the hood, the EvaluationRun is modeled as a Weave Call, and is stored as a Weave Trace. The canonical shape of the trace is:
* EvaluationRun
    * [Rows * Trials] Predict and Score
        * Predict
        * [Per Scorer Op] Score
    * Summarize
        * [Per Custom Scorer Object] Summarize
There is quite a lot of nuance here in the specific shape of the trace and inputs/outputs which are used to construct the evaluation UIs and analytics. Please see `weave-js/src/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/tsDataModelHooksEvaluationComparison.ts` for a detailed breakdown of how this data is extracted in the UI today.

## Current API

The current API looks a bit like this:

```python
# Define a Dataset
## Method 1: as list of rows
dataset = [{'x': 1}, {'x': 2}, {'x': 3}]

## Method 2: as a Weave Dataset
dataset = weave.Dataset(rows=[{'x': 1}, {'x': 2}, {'x': 3}])

# Define a Scorer
## Method 1: as an Op
@weave.op
def scorer_as_op(model_output, x):
    return model_output == x

## Method 2: as an Object
class ScorerAsObject(weave.Scorer):
    @weave.op
    def score(self, model_output, x):
        return model_output == x

    @weave.op
    def summarize(self, score_rows):
        return sum(score_rows) / len(score_rows)

# Define an Evaluation
evaluation = Evaluation(
    dataset=dataset,
    scorers=[scorer_as_op, ScorerAsObject()],
)

# Define a Model
## Method 1: as an Op
@weave.op
def predict(x):
    return x + 1

## Method 2: as an Object
class MyModel(weave.Model):
    @weave.op
    def predict(self, x):
        return x + 1

# Run the Evaluation
results = await evaluation.evaluate(model=model, n_trials=3)
```


## Challenges Identified

After shipping the current evaluation framework, we have identified a few challenges and limitations:

### Systemic Limitations
1. **Re-doing Work**: Currently, if a user wishes to make any chainge to their evaluation, the entire thing must be re-executed. This can be really painful and applies to all properties:
    * Dataset: If a single row is added or removed, the entire evaluation must be re-run.
    * Scorer: If a Scorer is added or removed, the entire evaluation must be re-run.
    * Trials: If we want to add some more trials for increased statistical significance, the entire evaluation must be re-run.
    Note: Shawn's original "Eval APIs" work was intended to address this specific issue by creating a mechanism for identifying the minimal amount of work needed to be done, and then only doing that work. However, at that time, we had not yet implemented a data model suitable for incremental evaluation runs.
2. **Up-front Dataset & Scorer Definition**: Curerntly you must define a dataset first, which is often the opposite of the the actual process -> where you collect examples over time and incrementally build up datasets and scorers
2. **Retroactive Scoring**: Users really want the ability to add scores to already-executed results. Let's say they have a production application, they want to add scores after the fact and analyze the results. Today, we don't support this use case.
3. **Proactive Scoring**: The alternative to retroactive scoring is proactive scoring. Users want the ability to add scores to new results as they are produced. This is close to the "gaurdrail" concept where you can define scoring methods to run on every new result.
4. **HITL Scoring**: Currently, we have the concept of "Feedback" in the application with the intention for it to support human-in-the-loop (HITL) workflows - ie. adding comments, ratings, labels, etc... However, as of today, there is no good way to integrate HITL feedback into evaluation results today.
5. **Out-of-Band Feedback**: Users want to be able to associate already-computed scores to their predictions - perhaps generated by a different, untracked system. Being locked into the Evaluation framework makes this extremely hard.
6. **(Future) Model Slots / Decomposed Tasks**: This is more of a future concept, but we will eventually want to make it possible to evaluate and analyze models that are composed of sub-models (where "model" is sometimes reffered to as a "slot" or "task"). This will require a much more general and flexible data model for evaluation results.

### Friction Points
1. **Parameter Coupling**: Currently, there is a 3-way coupling between the Dataset columns, the Scorer parameters, and the Model parameters. While this is easy to overcome in single evaluations, it makes sharing these assets difficult and error prone.
2. **Performance & Scalability**: Given that the current EvaluationRun data model is encoded in a Trace, queries and advanced analysis become challenging and overly complex - relying on trace topology and convention.
3. **Evaluations must be top level**: You cannot run an evaluation inside of another op - they must be trace-roots.


## Solution:
I have thoguht quite extensive about different options here, and I would like to propose what has bubbled up to the top as the most promising direction: "All you need is Feedback"

### All you need is Feedback

Interestingly, I think that nearly all of these challenges can be overcome with a simple idea: Store score results using our feedback data model as opposed to the Trace topology. _This is not a new idea_. In fact, I am pretty sure this is what Shawn wanted to use Feedback for all along. I'll now spend some time outlining more specifically what this looks like and how it addresses the challenges above.


* An "Evaluation Run" is just a definition of an evaluation.
* Everything is Feedback

### Grey Areas:
* How will custom aggregations work? Maybe they still are only applicable on EvaluationRuns?

### Followups
These are things that I would like to do, but are not MVP changes. I believe them to be important, but don't want to distract from the main proposal.
* Standardize Dataset Columns (Inputs, Labels)
* Standardize Model Prediction Format: (Model, Input) -> Output
* Standardize Score Format: (Output[, Inputs][, Labels]) -> Score




