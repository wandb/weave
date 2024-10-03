

# Supervised Section (Datsets with possible labels)

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