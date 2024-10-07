# Supervised Section (Datsets with possible labels)


import weave
from weave.flow.eval import Evaluation
from weave.trace import evaluation


def test_batch_eval():
    """
    This test deomonstrates the ability to run a batch evaluation in the traditional v1 sense)
    and validates that the resulting calls are correctly annotated with feedback scores according
    to the new data model spec.

    APIs used: Evaluation.evalute (or perhaps v2)
    """
    raise NotImplementedError()


def test_batch_eval_backfill():
    """
    This test demonstrates the the ability to backfill evaluation results which have already
    been partially completed. There are a few variants to consider:
    1. Exact match: Should be mostly a no-op.
    2. Add row(s) to the dataset.
    2.b: Variant: reduce the rows (no execution, just summarize differently)
    3. Add scorer(s) to the evaluation
    3.b: Variant: reduce the number of scorers (no execution, just summarize differently)
    4. Increase the trials
    4.b: Variant: reduce the trials (no execution, just summarize differently)
    5. Increase all
    5.b: Variant: reduce all

    APIs used: Evaluation.evalute (or perhaps v2)
    """
    raise NotImplementedError()


# Realtime Section (Gaurdrails on ops)


def test_realtime_op_level_scorers():
    """
    This test demonstrates the ability to add scorer(s) to an op itself
    which will be used to evaluate results in realitme.

    Additional check: Make sure that we can re-load ops with attached scorers

    APIs used: @weave.op(scorers=...)
    """
    raise NotImplementedError()


def test_realtime_call_time_scorers():
    """
    This test demonstrates the ability to include scorers at the moment of
    calling an op.

    APIs used: op.call(..., weave_call_options=...) or op(..., weave_call_options=...)
    """
    raise NotImplementedError()


# Retroactive Section


def test_retroactive_add_score():
    """
    This test demonstrates the ability to retroactively manually add
    a score that has been calculated externally. A more low-level operation.

    APIs used: call.add_score(...)
    """
    raise NotImplementedError()


def test_retroactive_apply_scorer():
    """
    This test demonstrates the ability to retroactively perform a scoring
    on a previously completed op call.

    variant: ability to only perform the scoring if needed

    APIs used: call.apply_scorer(...)
    """
    raise NotImplementedError()


def test_retroactive_batch_apply_score():
    """
    This test demonstrates the ability to retroactively apply
    a scoring function to a batch (query) of op calls

    variant: ability to only perform the scoring if needed

    APIs used: cleint.get_calls(query).apply_scorer(...)
    """
    raise NotImplementedError()


# Query Layer (still working out the details)


def test_calls_query_by_score():
    """
    This demonstrates the ability to query calls filtering or sorting based on scores. (Would be nice for general patterns to work for all feedback)

    Variants/Params:
    1. Type Filter (optional)
    2. User Filter (optional)
    3. Creator Filter (optional)
    4. Date Filter (optional)
    5. Mongo query against payload.
        Needs to determine how to resolve aggregations. (This point is actually one of the hardest right now)
        Specifically for scores, how do we specify which scorer ref (if at all) to use for a given score name? (also a hard one - maybe we always go with latest?)

    APIs used: client.get_calls(...)
    """
    raise NotImplementedError()


def test_grouped_calls_query():
    """
    This one is the hard one, but also the most powerful. We essentially want to be able to query
    the calls table, grouping by an input key, specify the score-level aggergation, specify the trial-level aggegation,
    then possibly sort or filter those final results! Very powerful.

    THis is used to create the view where each row is essentially a row in the dataset, and each

    APIs used: client.get_calls(...)
    """
    raise NotImplementedError()


def test_call_query_stats():
    """
    This demonstrates the ability to get column stats over a set of calls. Think: the queries
    used to create filter plots.

    Maybe we still do this in memory.

    """
    raise NotImplementedError()


# Lower-level integration utilities tests


def test_direct_create_generation():
    """
    This demonstrates the ability to directly create a "generation record" (name TBD)
    without using the op decorator. While this is available via the low-level rest API,
    it is still a bit cumbersome.

    API: client.log_generation(model_id, model_params, input, output, ...)
    """
    raise NotImplementedError()


"""
It might be worth thinking specifically aobut the views we want to create
and instead focusing on ensureing they can be represented. For example:

1. Given an Evaluation definition & a Model, build an interactive call table. Also, show the summary stats.
2. Given an Evaluation definition and Multiple models, build an interactive compare table (rows are dataset rows, columns are pivot on model and metrics)
3. Given a dataset row and a model, show the results aggregated over trials (for all scorers, or perhaps a specific scorer)
4. Given a dataset row and multiple models, show the comparison (aggregated over trials)

Thinking more about this, a score can be thought of as "latest" or a specific scorer version and multiple scores of the same version are meaningless (they should not be variable).

"""


def test_direct_log_generation_and_direct_log_score(client):
    """TODO: test all the new variants of different params"""
    generation = evaluation.log_generation(
        {"prompt": "Hello, what is your name?"}, "I'm sorry, I am an AI."
    )
    generation.log_score("contains_apology", True)

    calls = list(client.get_calls(include_feedback=True))
    assert len(calls) == 1
    call = calls[0]
    assert call.inputs["prompt"] == "Hello, what is your name?"
    assert call.output == "I'm sorry, I am an AI."
    # I would prefer to use the Calls.feedback edge, but it
    # is too complicated for me to just get the feedback out.
    call_feedback = call.summary["weave"]["feedback"]
    assert len(call_feedback) == 1
    feedback_item = call_feedback[0]
    assert feedback_item["feedback_type"] == "score"
    assert feedback_item["weave_ref"] == call.ref.uri()
    assert feedback_item["payload"] == {
        "name": "contains_apology",
        "op_ref": None,
        "call_ref": None,
        "supervision": None,
        "results": True,
    }
    assert feedback_item["creator"] is None
    assert feedback_item["created_at"] is not None
    assert feedback_item["wb_user_id"] is not None


def test_direct_log_generation_and_direct_apply_score(client):
    """TODO: test all the new variants of different params"""
    generation = evaluation.log_generation(
        {"prompt": "Hello, what is your name?"}, "I'm sorry, I am an AI."
    )

    @weave.op
    def contains_apology(model_output):
        return "sorry" in model_output

    generation.apply_scorer(contains_apology)

    calls = list(client.get_calls(include_feedback=True))
    assert len(calls) == 2
    call = calls[0]
    assert call.inputs["prompt"] == "Hello, what is your name?"
    assert call.output == "I'm sorry, I am an AI."

    score_call = calls[1]
    # assert score_call.inputs["inputs"] == call.inputs
    assert score_call.inputs["model_output"] == call.output
    # assert score_call.inputs["supervision"] == None
    assert score_call.output == True
    # I would prefer to use the Calls.feedback edge, but it
    # is too complicated for me to just get the feedback out.
    call_feedback = call.summary["weave"]["feedback"]
    assert len(call_feedback) == 1
    feedback_item = call_feedback[0]
    assert feedback_item["feedback_type"] == "score"
    assert feedback_item["weave_ref"] == call.ref.uri()
    assert feedback_item["payload"] == {
        "name": "contains_apology",
        "op_ref": score_call.op_name,
        "call_ref": score_call.ref.uri(),
        "supervision": None,
        "results": True,
    }
    assert feedback_item["creator"] is None
    assert feedback_item["created_at"] is not None
    assert feedback_item["wb_user_id"] is not None


def test_decorator_proactive(client):
    """TODO: test all the new variants of different params"""

    @weave.op
    def contains_apology(model_output):
        return "sorry" in model_output
    
    # TODO: Should we use a task here to reduce the duplication?

    @weave.op(scorers=[contains_apology])
    def make_generation(prompt: str) -> str:
        return "I'm sorry, I am an AI."

    res = make_generation("Hello, what is your name?")

    calls = list(client.get_calls(include_feedback=True))
    assert len(calls) == 2
    call = calls[0]
    assert call.inputs["prompt"] == "Hello, what is your name?"
    assert call.output == "I'm sorry, I am an AI."

    score_call = calls[1]
    # assert score_call.inputs["inputs"] == call.inputs
    assert score_call.inputs["model_output"] == call.output
    # assert score_call.inputs["supervision"] == None
    assert score_call.output == True
    # I would prefer to use the Calls.feedback edge, but it
    # is too complicated for me to just get the feedback out.
    call_feedback = call.summary["weave"]["feedback"]
    assert len(call_feedback) == 1
    feedback_item = call_feedback[0]
    assert feedback_item["feedback_type"] == "score"
    assert feedback_item["weave_ref"] == call.ref.uri()
    assert feedback_item["payload"] == {
        "name": "contains_apology",
        "op_ref": score_call.op_name,
        "call_ref": score_call.ref.uri(),
        "supervision": None,
        "results": True,
    }
    assert feedback_item["creator"] is None
    assert feedback_item["created_at"] is not None
    assert feedback_item["wb_user_id"] is not None


def test_smart_backfill(client):
    @weave.op
    def contains_apology(model_output):
        return "sorry" in model_output

    @weave.op()
    def make_generation(prompt: str) -> str:
        return "I'm sorry, I am an AI."

    make_generation("Hello, what is your name?")

    # TODO: Should we do a plan step?
    # TODO: can the stats be based on batches so this streams?
    stats = evaluation.backfill_scores(
        for_op=make_generation, scorers=[contains_apology]
    )

    assert stats["calls_found"] == 1
    assert stats["cache_hits"] == 0
    assert len(stats["score_records"]) == 1

    calls = list(client.get_calls(include_feedback=True))
    assert len(calls) == 2
    call = calls[0]
    assert call.inputs["prompt"] == "Hello, what is your name?"
    assert call.output == "I'm sorry, I am an AI."

    score_call = calls[1]
    # assert score_call.inputs["inputs"] == call.inputs
    assert score_call.inputs["model_output"] == call.output
    # assert score_call.inputs["supervision"] == None
    assert score_call.output == True
    # I would prefer to use the Calls.feedback edge, but it
    # is too complicated for me to just get the feedback out.
    call_feedback = call.summary["weave"]["feedback"]
    assert len(call_feedback) == 1
    feedback_item = call_feedback[0]
    assert feedback_item["feedback_type"] == "score"
    assert feedback_item["weave_ref"] == call.ref.uri()
    assert feedback_item["payload"] == {
        "name": "contains_apology",
        "op_ref": score_call.op_name,
        "call_ref": score_call.ref.uri(),
        "supervision": None,
        "results": True,
    }
    assert feedback_item["creator"] is None
    assert feedback_item["created_at"] is not None
    assert feedback_item["wb_user_id"] is not None

    @weave.op
    def contains_period(model_output):
        return "." in model_output

    make_generation("Please tell me!")

    stats = evaluation.backfill_scores(
        for_op=make_generation, scorers=[contains_apology, contains_period]
    )

    assert stats["calls_found"] == 2
    assert stats["cache_hits"] == 1  # 1 prior score / op combo
    assert len(stats["score_records"]) == 3  # 3 new "cells" to fill


# TODO: Need input hashing for thie to actually work efficiently.
# Plan: hash(inputs_with_hash_keys)
# Might also want to have some otehr identifiers for a call:
# {
#   inputs_hash -> good for logs outside the framework (server-side calc)
#   dataset_row_hash -> good to logs created with eval framework (normally would be same as inputs_hash unless the model inputs vary)
#   example_id -> user-defined example ID might be useful for comparison across datasets with equal rows.
# }
# def test_smart_forward_fill(client):
#     @weave.op
#     def contains_apology(model_output):
#         return "sorry" in model_output

#     @weave.op()
#     def make_generation(prompt: str) -> str:
#         return "I'm sorry, I am an AI."

    # plan_object -> costs, stream...
    # stats = evaluation.forwardfill_scores(
    #     for_op=make_generation, scorers=[contains_apology], dataset=[{
    #         "prompt": "Hello, what is your name?"
    #     }]
    # )

#     assert stats["calls_found"] == 1
#     assert stats["cache_hits"] == 0
#     assert len(stats["score_records"]) == 1

#     calls = list(client.get_calls(include_feedback=True))
#     assert len(calls) == 2
#     call = calls[0]
#     assert call.inputs["prompt"] == "Hello, what is your name?"
#     assert call.output == "I'm sorry, I am an AI."

#     score_call = calls[1]
#     # assert score_call.inputs["inputs"] == call.inputs
#     assert score_call.inputs["model_output"] == call.output
#     # assert score_call.inputs["supervision"] == None
#     assert score_call.output == True
#     # I would prefer to use the Calls.feedback edge, but it
#     # is too complicated for me to just get the feedback out.
#     call_feedback = call.summary["weave"]["feedback"]
#     assert len(call_feedback) == 1
#     feedback_item = call_feedback[0]
#     assert feedback_item["feedback_type"] == "score"
#     assert feedback_item["weave_ref"] == call.ref.uri()
#     assert feedback_item["payload"] == {
#         "name": "contains_apology",
#         "op_ref": score_call.op_name,
#         "call_ref": score_call.ref.uri(),
#         "supervision": None,
#         "results": True,
#     }
#     assert feedback_item["creator"] is None
#     assert feedback_item["created_at"] is not None
#     assert feedback_item["wb_user_id"] is not None

#     @weave.op
#     def contains_period(model_output):
#         return "." in model_output

#     make_generation("Please tell me!")

#     stats = evaluation.backfill_scores(
#         for_op=make_generation, scorers=[contains_apology, contains_period]
#     )

#     assert stats["calls_found"] == 2
#     assert stats["cache_hits"] == 1  # 1 prior score / op combo
#     assert len(stats["score_records"]) == 3  # 3 new "cells" to fill


def test_eval_backfill(client):
    @weave.op
    def contains_apology(model_output):
        return "sorry" in model_output

    @weave.op(scorers=[contains_apology])
    def make_generation(prompt: str) -> str:
        return "I'm sorry, I am an AI."

    eval_v1 = Evaluation(
        dataset=[{"prompt": "Hello, what is your name?"}], scorers=[contains_apology]
    )

    eval_v1.evaluate(make_generation)

    # res = make_generation("Hello, what is your name?")

    # calls = list(client.get_calls(include_feedback=True))
    # assert len(calls) == 2
    # call = calls[0]
    # assert call.inputs["prompt"] == "Hello, what is your name?"
    # assert call.output == "I'm sorry, I am an AI."

    # score_call = calls[1]
    # assert score_call.inputs["inputs"] == call.inputs
    # assert score_call.inputs["output"] == call.output
    # assert score_call.inputs["supervision"] == None
    # assert score_call.output == True
    # # I would prefer to use the Calls.feedback edge, but it
    # # is too complicated for me to just get the feedback out.
    # call_feedback = call.summary["weave"]["feedback"]
    # assert len(call_feedback) == 1
    # feedback_item = call_feedback[0]
    # assert feedback_item["feedback_type"] == "score"
    # assert feedback_item["weave_ref"] == call.ref.uri()
    # assert feedback_item["payload"] == {
    #     "name": "contains_apology",
    #     "op_ref": score_call.op_name,
    #     "call_ref": score_call.ref.uri(),
    #     "supervision": None,
    #     "results": True,
    # }
    # assert feedback_item["creator"] is None
    # assert feedback_item["created_at"] is not None
    # assert feedback_item["wb_user_id"] is not None


"""
Notes to self:
2. Make a smart forward-fill (needs to leverage the ID stuff - this might allow us to get rid of some refs?
    2.a) Explore if we can get rid of refs completely? Perhaps just by having a ref-map in the attributes?!??! - is it that easy?
    {
        [input_key]: hash,

    }
3. Rework evaluations to have a cache-based option:
    1. Use Smart foward-fill to calculate the needed rows
    2. Use smart backfill to calculate the scores
    3. Summarize the data and log the evaluation run
4. Make a UI that can look at an evaluation definition and render the results
    1. Converting the query layer to this new model for evals marked as "cached" - the query layer should be much faster
5. Make a UI that can take any call table and render the pivoted comparison (it need not be limited by a speicfic dataset or score-set. Evaluation summary is the only thing missing)
    5.b: Add the summary to the backend calculation for these dynamic results.

Bug:
* need to make eval stuff backgrounded!

Probably want to cleanup the names of everyting
Obviously: a bunch of cleanup and little todos & magic stuff



Properties from Shawn:
* Trials need to be first class
* Steaming
* Caching
* Cost Estimation
"""
