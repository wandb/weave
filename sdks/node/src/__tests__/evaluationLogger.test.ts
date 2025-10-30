/**
 * Unit tests for EvaluationLogger (Imperative Evaluation)
 */

import {EvaluationLogger} from '../evaluationLogger';
import {WeaveObject} from '../weaveObject';
import {initWithCustomTraceServer} from './clientMock';
import {InMemoryTraceServer} from '../inMemoryTraceServer';

// Helper function to get calls from trace server
async function getCalls(traceServer: InMemoryTraceServer, projectId: string) {
  // Wait for async batch processing to complete
  await traceServer.waitForPendingOperations();

  return traceServer.calls
    .callsStreamQueryPost({
      project_id: projectId,
    })
    .then(result => result.calls);
}

describe('EvaluationLogger - Basic Functionality', () => {
  let traceServer: InMemoryTraceServer;
  const projectId = 'test-project';

  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(projectId, traceServer);
  });

  // Test: Basic flow - logPredictionAsync → logScore → finish → logSummary (awaitable API)
  test('complete evaluation lifecycle', async () => {
    const evalLogger = new EvaluationLogger({name: 'test-eval'});

    const scoreLogger = await evalLogger.logPredictionAsync(
      {input: 'test'},
      'output'
    );

    await scoreLogger.logScore('accuracy', 0.95);
    await scoreLogger.logScore('f1', 0.88);
    await scoreLogger.finish();
    await evalLogger.logSummary();

    const calls = await getCalls(traceServer, projectId);
    expect(calls.length).toBeGreaterThan(0);
  });

  // Test: Fire-and-forget with chained calls - true synchronous API
  test('fire-and-forget with chained calls', async () => {
    const evalLogger = new EvaluationLogger({name: 'test-eval'});

    // True fire-and-forget: synchronous, no await needed!
    const scoreLogger = evalLogger.logPrediction({input: 'test'}, 'output');

    // Fire-and-forget: call methods without awaiting
    scoreLogger.logScore('accuracy', 0.95);
    scoreLogger.logScore('f1', 0.88);
    scoreLogger.finish();

    // logSummary waits for everything to complete internally
    await evalLogger.logSummary();

    const calls = await getCalls(traceServer, projectId);
    expect(calls.length).toBeGreaterThan(0);

    // Verify scores were logged
    const predictAndScoreCall = calls.find(c =>
      c.op_name?.includes('predict_and_score')
    );
    expect(predictAndScoreCall?.output?.scores?.accuracy).toBe(0.95);
    expect(predictAndScoreCall?.output?.scores?.f1).toBe(0.88);
  });

  // Test: Fire-and-forget with chained calls - true synchronous API
  test('fire-and-forget usage with multple threads', async () => {
    const evalLogger = new EvaluationLogger({name: 'test-eval'});

    // True fire-and-forget: synchronous, no await needed!
    const scoreLogger = evalLogger.logPrediction({input: 'test'}, 'output');

    // Fire-and-forget: call methods without awaiting
    scoreLogger.logScore('accuracy', 0.3);
    scoreLogger.logScore('f1', 0.9);
    scoreLogger.finish();

    const scoreLogger2 = evalLogger.logPrediction({input: 'test'}, 'output');

    // Fire-and-forget: call methods without awaiting
    scoreLogger2.logScore('accuracy', 0.4);
    scoreLogger2.logScore('f1', 0.7);
    scoreLogger2.finish();

    const scoreLogger3 = evalLogger.logPrediction({input: 'test'}, 'output');

    // Fire-and-forget: call methods without awaiting
    scoreLogger3.logScore('accuracy', 0.5);
    scoreLogger3.logScore('f1', 0.8);
    scoreLogger3.finish();

    // logSummary waits for everything to complete internally
    await evalLogger.logSummary();

    const calls = await getCalls(traceServer, projectId);
    expect(calls.length).toBeGreaterThan(0);

    // Verify scores were logged
    const summarizeCall = calls.find(c => c.op_name?.includes('summarize'));
    const output = summarizeCall?.output;
    expect(output?.accuracy?.mean).toBeCloseTo(0.4, 2);
    expect(output?.f1?.mean).toBeCloseTo(0.8, 2);
  });

  // Test: Auto-finish when logSummary is called without explicit finish()
  test('auto-finishes predictions when logSummary is called', async () => {
    const evalLogger = new EvaluationLogger({name: 'test-eval'});

    const scoreLogger = await evalLogger.logPredictionAsync(
      {input: 'test'},
      'output'
    );
    await scoreLogger.logScore('accuracy', 0.95);
    // Intentionally don't call finish()

    // logSummary should auto-finish and complete successfully
    await evalLogger.logSummary();

    const calls = await getCalls(traceServer, projectId);
    const predictAndScoreCall = calls.find(c =>
      c.op_name?.includes('predict_and_score')
    );

    // Verify the prediction was properly finished
    expect(predictAndScoreCall?.output?.scores?.accuracy).toBe(0.95);
  });

  // Test: EvaluationLogger accepts all configuration options
  test('accepts full configuration options', async () => {
    const model = new WeaveObject({name: 'my-model'});

    const evalLogger = new EvaluationLogger({
      name: 'test-eval',
      description: 'Test evaluation',
      dataset: 'dummy-dataset',
      model,
      scorers: ['accuracy', 'f1'],
      attributes: {trial_id: 'abc123'},
    });

    const scoreLogger = await evalLogger.logPredictionAsync(
      {input: 'test'},
      'out'
    );
    await scoreLogger.finish();
    await evalLogger.logSummary();

    const calls = await getCalls(traceServer, projectId);
    const evaluateCall = calls.find(c => c.op_name?.includes('evaluate'));

    expect(evaluateCall?.attributes?.trial_id).toBe('abc123');
  });
});

describe('EvaluationLogger - Call Hierarchy', () => {
  let traceServer: InMemoryTraceServer;
  const projectId = 'test-project';

  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(projectId, traceServer);
  });

  // Test: Verify complete call tree structure
  test('creates correct parent-child relationships', async () => {
    const evalLogger = new EvaluationLogger({name: 'test-eval'});
    const scoreLogger = await evalLogger.logPredictionAsync(
      {input: 'test'},
      'output'
    );
    scoreLogger.logScore('accuracy', 0.95);
    await scoreLogger.finish();
    await evalLogger.logSummary();

    const calls = await getCalls(traceServer, projectId);
    const evaluateCall = calls.find(c => c.op_name?.includes('evaluate'));
    const predictAndScoreCall = calls.find(c =>
      c.op_name?.includes('predict_and_score')
    );
    const predictCall = calls.find(
      c => c.op_name?.includes('predict') && !c.op_name?.includes('_and_')
    );
    const scorerCall = calls.find(c => c.op_name?.includes('accuracy'));
    const summarizeCall = calls.find(c => c.op_name?.includes('summarize'));

    // evaluate is root
    expect(evaluateCall?.parent_id).toBeUndefined();

    // predict_and_score and summarize are children of evaluate
    expect(predictAndScoreCall?.parent_id).toBe(evaluateCall?.id);
    expect(summarizeCall?.parent_id).toBe(evaluateCall?.id);

    // predict and scorer are children of predict_and_score
    expect(predictCall?.parent_id).toBe(predictAndScoreCall?.id);
    expect(scorerCall?.parent_id).toBe(predictAndScoreCall?.id);
  });
});

describe('EvaluationLogger - Attribute Markers', () => {
  let traceServer: InMemoryTraceServer;
  const projectId = 'test-project';
  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(projectId, traceServer);
  });

  // Test: IMPERATIVE_EVAL_MARKER on eval calls
  test('adds IMPERATIVE_EVAL_MARKER to evaluation calls', async () => {
    const evalLogger = new EvaluationLogger({name: 'test-eval'});
    const scoreLogger = await evalLogger.logPredictionAsync(
      {input: 'test'},
      'output'
    );
    await scoreLogger.finish();
    await evalLogger.logSummary();

    const calls = await getCalls(traceServer, projectId);
    const evaluateCall = calls.find(c => c.op_name?.includes('evaluate'));
    const predictCall = calls.find(
      c => c.op_name?.includes('predict') && !c.op_name?.includes('_and_')
    );
    const summarizeCall = calls.find(c => c.op_name?.includes('summarize'));

    expect(evaluateCall?.attributes?._weave_eval_meta?.imperative).toBe(true);
    expect(predictCall?.attributes?._weave_eval_meta?.imperative).toBe(true);
    expect(summarizeCall?.attributes?._weave_eval_meta?.imperative).toBe(true);
  });

  // Test: IMPERATIVE_SCORE_MARKER on scorer calls
  test('adds IMPERATIVE_SCORE_MARKER to scorer calls', async () => {
    const evalLogger = new EvaluationLogger({name: 'test-eval'});
    const scoreLogger = await evalLogger.logPredictionAsync(
      {input: 'test'},
      'output'
    );
    scoreLogger.logScore('accuracy', 0.95);
    await scoreLogger.finish();
    await evalLogger.logSummary();

    const calls = await getCalls(traceServer, projectId);
    const scorerCall = calls.find(c => c.op_name?.includes('accuracy'));

    expect(scorerCall?.attributes?._weave_eval_meta?.imperative).toBe(true);
    expect(scorerCall?.attributes?._weave_eval_meta?.score).toBe(true);
  });
});

describe('EvaluationLogger - Summary Generation', () => {
  let traceServer: InMemoryTraceServer;
  const projectId = 'test-project';
  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(projectId, traceServer);
  });

  // Test: Auto-summary calculates mean for numeric scores
  test('auto-summary calculates mean for numeric scores', async () => {
    const evalLogger = new EvaluationLogger({name: 'test-eval'});

    for (let i = 0; i < 3; i++) {
      const scoreLogger = await evalLogger.logPredictionAsync(
        {input: `test${i}`},
        `output${i}`
      );
      scoreLogger.logScore('accuracy', 0.9 + i * 0.05);
      await scoreLogger.finish();
    }

    await evalLogger.logSummary();

    const calls = await getCalls(traceServer, projectId);
    const evaluateCall = calls.find(c => c.op_name?.includes('evaluate'));

    expect(evaluateCall?.output?.accuracy?.mean).toBeCloseTo(0.95, 2);
  });

  // Test: Auto-summary calculates true_count and true_fraction for boolean scores
  test('auto-summary calculates true_fraction for boolean scores', async () => {
    const evalLogger = new EvaluationLogger({name: 'test-eval'});

    const scoreLogger1 = await evalLogger.logPredictionAsync(
      {input: '1'},
      'out1'
    );
    scoreLogger1.logScore('passed', true);
    await scoreLogger1.finish();

    const scoreLogger2 = await evalLogger.logPredictionAsync(
      {input: '2'},
      'out2'
    );
    scoreLogger2.logScore('passed', false);
    await scoreLogger2.finish();

    const scoreLogger3 = await evalLogger.logPredictionAsync(
      {input: '3'},
      'out3'
    );
    scoreLogger3.logScore('passed', true);
    await scoreLogger3.finish();

    await evalLogger.logSummary();

    const calls = await getCalls(traceServer, projectId);
    const evaluateCall = calls.find(c => c.op_name?.includes('evaluate'));

    expect(evaluateCall?.output?.passed?.true_count).toBe(2);
    expect(evaluateCall?.output?.passed?.true_fraction).toBeCloseTo(2 / 3, 2);
  });

  // Test: Custom summary can override auto-summary
  test('custom summary overrides auto-summary', async () => {
    const evalLogger = new EvaluationLogger({name: 'test-eval'});

    const scoreLogger = await evalLogger.logPredictionAsync(
      {input: 'test'},
      'output'
    );
    scoreLogger.logScore('accuracy', 0.95);
    await scoreLogger.finish();

    await evalLogger.logSummary({
      custom_metric: 'custom_value',
      accuracy: {mean: 0.99},
    });

    const calls = await getCalls(traceServer, projectId);
    const evaluateCall = calls.find(c => c.op_name?.includes('evaluate'));

    expect(evaluateCall?.output?.custom_metric).toBe('custom_value');
    expect(evaluateCall?.output?.accuracy?.mean).toBe(0.99);
  });
});

describe('EvaluationLogger - Edge Cases', () => {
  let traceServer: InMemoryTraceServer;
  const projectId = 'test-project';
  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(projectId, traceServer);
  });

  // Test: Prediction with no scores
  test('handles prediction with no scores', async () => {
    const evalLogger = new EvaluationLogger({name: 'test-eval'});

    const scoreLogger = await evalLogger.logPredictionAsync(
      {input: 'test'},
      'output'
    );
    await scoreLogger.finish();

    await evalLogger.logSummary();

    const calls = await getCalls(traceServer, projectId);
    const predictAndScoreCall = calls.find(c =>
      c.op_name?.includes('predict_and_score')
    );

    expect(predictAndScoreCall?.output?.scores).toEqual({});
  });

  // Test: Summary with no predictions
  test('handles summary with no predictions', async () => {
    const evalLogger = new EvaluationLogger({name: 'test-eval'});

    await evalLogger.logSummary();

    const calls = await getCalls(traceServer, projectId);
    const evaluateCall = calls.find(c => c.op_name?.includes('evaluate'));

    expect(evaluateCall).toBeDefined();
    expect(evaluateCall?.output).toEqual({});
  });

  // Test: Multiple predictions work correctly
  test('handles multiple predictions sequentially', async () => {
    const evalLogger = new EvaluationLogger({name: 'test-eval'});

    for (let i = 0; i < 5; i++) {
      const scoreLogger = await evalLogger.logPredictionAsync(
        {input: `test${i}`},
        `output${i}`
      );
      scoreLogger.logScore('accuracy', 0.9);
      await scoreLogger.finish();
    }

    await evalLogger.logSummary();

    const calls = await getCalls(traceServer, projectId);
    const predictAndScoreCalls = calls.filter(c =>
      c.op_name?.includes('predict_and_score')
    );

    expect(predictAndScoreCalls.length).toBe(5);
  });
});
