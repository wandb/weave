# CodeScorer

`CodeScorer` lets users bring arbitrary Python code into Weave's online evaluation
pipeline. The scoring logic is defined like any other `Scorer`, but when triggered
by an online monitor the worker executes `score()` in an isolated sandbox instead
of in-process, so user-defined dependencies and untrusted code stay safely
contained.

---

## User-facing API

### Define a scorer

Subclass `CodeScorer` and implement `score()` exactly as you would any
`weave.Scorer`. Declare the extra packages your code needs in `requirements`, or
supply a fully-baked `docker_image`.

```python
import weave
from weave.flow.code_scorer import CodeScorer

class RougeScorer(CodeScorer):
    requirements: list[str] = ["rouge-score>=0.1"]

    @weave.op
    def score(self, *, output: str, reference: str) -> dict:
        from rouge_score import rouge_scorer
        scorer = rouge_scorer.RougeScorer(["rougeL"])
        result = scorer.score(reference, output)
        return {"rougeL": result["rougeL"].fmeasure}
```

`requirements` and `docker_image` are mutually exclusive. `docker_image` is for
teams that already maintain a container with their full ML environment baked in.

### Publish and attach to an online monitor

```python
weave.init("my-entity/my-project")

scorer = RougeScorer(name="rouge-scorer")
weave.publish(scorer)

# Attach to a monitor via the UI or API — the scorer ref is what gets stored.
```

### Offline evaluation — no sandbox, no change

`CodeScorer` is a normal `Scorer`. Offline evaluation works identically to any
other scorer; the sandbox path is only taken server-side.

```python
evaluation = weave.Evaluation(
    dataset=dataset,
    scorers=[RougeScorer(requirements=["rouge-score>=0.1"])],
)
await evaluation.evaluate(model)  # score() runs locally, as usual
```

---

## How the scoring worker executes a CodeScorer

```
Kafka message
    │  (project_id, call_ids, scorer_refs)
    ▼
CallScoringWorker / ScoringWorker
    │
    ├─ resolve_scorer_refs()   ← deserializes scorer object from DB
    │                            (CodeScorer fields: requirements, docker_image,
    │                             secrets, and the score @op ref)
    │
    └─ _do_score_call()
           │
           ├─ isinstance(scorer, LLMAsAJudgeScorer)  → LLM path
           ├─ isinstance(scorer, CodeScorer)          → sandbox path  ← new
           └─ else                                    → direct resolve_fn call
```

### Sandbox path detail

1. **Fetch the score op source.**
   Because `score()` is decorated with `@weave.op`, its source code is stored in
   Weave when the scorer is published. The worker fetches it via `refs_read_batch`.

2. **Prepare score args.**
   `prepare_scorer_op_args()` maps the call's inputs and output to the scorer's
   parameter names, exactly as for any other scorer.

3. **Spin up a Modal sandbox.**
   The worker creates an ephemeral sandbox (Modal, matching the approach used by
   the `wb_agent` service). The sandbox receives:
   - `WANDB_API_KEY` (service account key for `weave.init`)
   - `WEAVE_PROJECT` (`entity/project`)
   - Any user-declared `secrets`, fetched from the entity's secret store

4. **Install the environment.**
   - `requirements` → `uv pip install <packages>` inside the sandbox
   - `docker_image` → the sandbox is created from that image directly; no install step

5. **Execute the scoring script.**
   The worker generates and runs a small Python script:

   ```python
   import json, sys, weave

   weave.init("<entity>/<project>")

   score_args  = json.loads(sys.argv[1])   # serialized call inputs + output
   scorer_data = json.loads(sys.argv[2])   # scorer field values (e.g. threshold)

   # score() source code is exec'd here with scorer_data as instance fields
   # result is printed as JSON to stdout
   ```

6. **Collect the result.**
   stdout is parsed as JSON. The result is treated identically to any other
   scorer's output — it goes through `auto_summarize`, is stored as a
   `call_start`/`call_end` pair, and written as a `RUNNABLE_FEEDBACK` entry
   attached to the original call.

7. **Tear down.**
   The sandbox is terminated regardless of success or failure.

### Error handling

If the sandbox exits non-zero, the exception is captured in the same structure
used for LLM scorer errors:

```json
{"type": "RuntimeError", "message": "..."}
```

This is stored on the `call_end` record. No feedback entry is created (matching
the existing behavior for failed scorers). The worker does not retry — the call
will be rescored on the next monitor cycle if it still matches the filter.

---

## Object model

| Field | Type | Purpose |
|---|---|---|
| `requirements` | `list[str] \| None` | Packages installed via `uv pip install` |
| `docker_image` | `str \| None` | Base container image (mutually exclusive with `requirements`) |
| `secrets` | `list[str] \| dict[str,str] \| None` | Entity secrets injected as env vars |
| `column_map` | `dict[str,str] \| None` | Inherited from `Scorer` — remap dataset columns to score() params |

`requirements` and `docker_image` are mutually exclusive. At least one must be set.

---

## Security model

- The sandbox has no access to weave-trace internal infrastructure.
- Network access from the sandbox is limited to what Modal permits; no direct
  ClickHouse or Kafka access is possible.
- User code authenticates to Weave via a scoped API key — it can read/write
  objects and calls within its project, nothing else.
- Secrets are fetched from the entity's secret store by the worker (not the user)
  and injected as env vars; the user code never sees the secret-fetching
  credentials.
- The sandbox is torn down after every individual score call; no state persists
  between invocations.
