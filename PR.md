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
2. **Up-front Dataset & Scorer Definition**: Currently you must define a dataset first, which is often the opposite of the the actual process -> where you collect examples over time and incrementally build up datasets and scorers
2. **Retroactive Scoring**: Users really want the ability to add scores to already-executed results. Let's say they have a production application, they want to add scores after the fact and analyze the results. Today, we don't support this use case.
3. **Proactive Scoring**: The alternative to retroactive scoring is proactive scoring. Users want the ability to add scores to new results as they are produced. This is close to the "gaurdrail" concept where you can define scoring methods to run on every new result.
4. **HITL Scoring**: Currently, we have the concept of "Feedback" in the application with the intention for it to support human-in-the-loop (HITL) workflows - ie. adding comments, ratings, labels, etc... However, as of today, there is no good way to integrate HITL feedback into evaluation results today.
5. **Out-of-Band Feedback**: Users want to be able to associate already-computed scores to their predictions - perhaps generated by a different, untracked system. Being locked into the Evaluation framework makes this extremely hard.
6. **(Future) Model Slots / Decomposed Tasks**: This is more of a future concept, but we will eventually want to make it possible to evaluate and analyze models that are composed of sub-models (where "model" is sometimes reffered to as a "slot" or "task"). This will require a much more general and flexible data model for evaluation results.

### Friction Points
1. **Parameter Coupling**: Currently, there is a 3-way coupling between the Dataset columns, the Scorer parameters, and the Model parameters. While this is easy to overcome in single evaluations, it makes sharing these assets difficult and error prone.
2. **Evaluating Scorers**: It is not really clear today how one would go about evaluating a scorer - it is possible, but not at all clear or straightforward.
3. **Performance & Scalability**: Given that the current EvaluationRun data model is encoded in a Trace, queries and advanced analysis become challenging and overly complex - relying on trace topology and convention.
4. **Evaluations must be top level**: You cannot run an evaluation inside of another op - they must be trace-roots.


## Solution: All you need is Feedback
I have thoguht quite extensive about different options here, and I would like to propose what has bubbled up to the top as the most promising direction: "All you need is Feedback". Interestingly, I think that nearly all of these challenges can be overcome with a simple idea: Store score results using our feedback data model as opposed to the Trace topology. _This is not a new idea_. In fact, I am pretty sure this is what Shawn wanted to use Feedback for all along. I'll now spend some time outlining more specifically what this looks like and how it addresses the challenges above.

### Background on Feedback
Feedback is modeled in Weave as a list of FeedbackDicts, where `weave_ref` is a reference to a specific Call. Each FeedbackDict has a `feedback_type` which is used to categorize the type of feedback, and a `payload` which is used to store any additional data the user wants to store. Currently, we use this data model to store user feedback in the form of notes and emojis.
```
class FeedbackDict(TypedDict, total=False):
    id: str
    feedback_type: str
    weave_ref: str
    payload: Dict[str, Any]
    creator: Optional[str]
    created_at: Optional[datetime.datetime]
    wb_user_id: Optional[str]
```

### Proposal

#### Data Model
We create a new Feedback type: "score" (we might want a few, but the point is we store them here). The exact payload is in flux, but likely have something like the following properties:
    * `call_ref`: The ref of the call that generated the score
    * `op_ref`: The op that was used to generate the score
        * Note: this is technically denormalization
    * `score_args`: The arguments passed to the op to generate the score (not sure if it should duplicate the inputs yet)
        * Note: this is technically denormalization
    * `result`: The result of the scorer

* We will keep the `Evaluation` object itself for now - it is very useful.
* We will keep the `EvaluationRun` call for now, but not rely on the topology anymore. It will still be useful to to have summizations stored on the call output!

#### API
There is really only 1 new concept for user: Adding scores to calls. The exact APIs can be debated, but fundamntally, I think we will need:
* `Evaluation.evaluate(...)`: Yes! This already exists! The evaluation framework can stay as-is and under the hood:
    * 1. Attach scores to the predict calls without the user even knowing.
    * 2. Intelligently sub-select which predictions and scores are needed to "backfill" the evaluation.
* `Call.apply_scorer(score_fn)`: allows a user to apply a scorer to a call - useful for one-off scoring events or scoring from a query of calls.
* Open Ideas:
    * `@weave.op(scorers=[])`: allows a user to define scorers that should run for every single prediction (realtime scoring).
* Beyond MVP:
    * `Call.add_score(...)`: this is a slightly lower level API that would allow a user to add a score to a call without running a scorer directly.
    * `POST score/add` http endpoint that facilitates adding these scores. However, for now, we will just use the lower-level feedback API.
* Sugar:
    * `client.calls(query).apply_scorer(op)`: syntactic sugar for scoring in batch.
    * `op(*args, **kwargs, weave_call_options={scorers: []})`: syntatic sugar for scoring integrations like OpenAI or any Op which you don't have the definition for. You could do `op.call(...).apply_scorer(score_fn)`, but this is cleaner.

#### Query-Side Changes:
* We need to be able to filter/sort on Feedback fields on calls.

#### UI Changes:
* Now, we can take any Call Table view and have a charts section with scores
* Looking at an evaluation, we can give the user code to backfill it
* The evaluation UI becomes much much faster
    
#### Use Cases?
Ok, this is a lot of talk, how does this actually unlock new workflows for users?

Step 1: No dataset, no scorers, just a few predictions in the system:
* Open the UI, add some feedback, start to see some metrics on that feedback

Step 2: Your first scorer:
* Start to anlyze the patterns and write a simple unlabelled scorer
* Add it to your op to see scores start flowing in
```python
@weave.op(scorers=[my_scorer])
```

Step 3: Backfill the scores
* Decide to backfill all the scores for a specific view:
```python
client.calls(query).apply_scorer(my_scorer)
```

Step 4: Build a dataset
TODO: This is not easy today!

Step 6: Run standard evaluation
```python
evaluation = Evaluation(
    dataset=dataset,
    scorers=[my_scorer],
)
results = await evaluation.evaluate(model=model, n_trials=3)
```

Step 7: Analyze richly in the UI
TODOL: make the join view!

Step 7: Iterate on scorers & datasets, cheeply
```python
evaluation = Evaluation(
    dataset=dataset_v2,
    scorers=[my_scorer, my_other_scorer],
)
results = await evaluation.evaluate(model=model, n_trials=3)
```

Bonus: Evaluating Scorers:
TODO: Fillout

#### Addressing Challenges
Copying the challenges from the previous section, I will now describe how the new data model will help us address these challenges:
1. **Re-doing Work**: Calling the same `evaluation.evaluate` twice in a row would result in effectively a no-op on the second call! Remember, if we don't need the trace topology, we can skip a bunch of work! The framework can:
    1. Query to determine which predictions are needed, and only run those predict ops.
    2. Based on the attached feedback, determine which scorers should run and only run those scorers.
    3. Aggregate the composite results.
2. **Up-front Dataset & Scorer Definition**: Given the above, this item is unlocked! 
    * Note: there is a subtlty here that this really doesn't become very good until we have "Add to dataset".
2. **Retroactive Scoring**: This is now completely supported! Just 
3. **Proactive Scoring**: This can be achieved with the decorator API described above.
4. **HITL Scoring**: Amazingly, we can use all the same aggregation mechanics on feedback to support HITL!
5. **Out-of-Band Feedback**: Unlocked with the "Beyond MVP" section.
6. **(Future) Model Slots / Decomposed Tasks**: This is now unlocked with the ability to directly associate feedback with a call.
7. **Parameter Coupling**: This is not solved immediately, but is addressed in the "Less important followups" section below.
8. **Evaluating Scorers**: This is demonstrated in the "Use Cases" section above.
9. **Performance & Scalability**: Yes, much much faster (assuming the feedback join is relatively efficient)
4. **Evaluations must be top level**: Solved!

#### Considerations
* We might need to aggregate scorers if they are non-deterministic as well.

#### Less important followups
These are things that I would like to do, but are not MVP changes. I believe them to be important, but don't want to distract from the main proposal. Basically this is all about standardardizing the params and shapes to make things more consistent.
* **Standardize Dataset Columns  (Inputs, Labels)**: Until now, Datasets can have any shape. I think they should explicilty have an Inputs column and a Labels column. The Inputs column can be a dictionary of values, and the labels column is a list of dictionaries. This would allow us to have: unlabble datasets and a standard pattern for "add to dataset". For example, if you want to add an existing prediction to a dataset, you can add just the inputs, or the inputs and the outputs (where the output is now one of many labels), or even feedback.
* **Standardize Model Prediction Format: (Model, Input) -> Output**: Similarly, we should have a standard format for the model prediction. This would really help to ensure any model can fit anywhere.
* **Standardize Score Format: (Output[, Inputs][, Labels]) -> Score**: There are actually 3 types of scorers - those that just operate on the output, those that operate on the output and inputs, and those that operate on the output and labels. We should use standard columns here to make things more consistent and easier to work with.




