/**
 * Imperative Evaluation Logger
 *
 * This module provides an alternative to the traditional batch-oriented Evaluation class.
 * It allows incremental logging of predictions and scores as they happen, without requiring
 * a fixed dataset or batch processing.
 *
 * @example
 * const ev = new EvaluationLogger();
 * for (const example of streamingDataSource) {
 *   const output = await myModel.predict(example);
 *   const pred = await ev.logPrediction(example, output);
 *   await pred.logScore("accuracy", calculateScore(output));
 *   await pred.finish();
 * }
 * await ev.logSummary();
 */

import {WeaveObject, WeaveObjectParameters} from './weaveObject';
import {Dataset} from './dataset';
import {op} from './op';
import {requireGlobalClient} from './clientApi';
import {InternalCall} from './call';
import {CallStackEntry} from './weaveClient';
import {uuidv7} from 'uuidv7';

// ============================================================================
// Attribute Markers (matching Python SDK)
// ============================================================================

/**
 * Attribute marker for imperative evaluation calls.
 * Applied to: evaluate, predict_and_score, predict, summarize calls.
 */
const IMPERATIVE_EVAL_MARKER = {_weave_eval_meta: {imperative: true}};

/**
 * Attribute marker for scorer calls in imperative evaluation.
 * Applied to: scorer.score calls.
 */
const IMPERATIVE_SCORE_MARKER = {
  _weave_eval_meta: {imperative: true, score: true},
};

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Utility to create and immediately finish a call in the same function frame.
 * This is used for calls where we already know the output (predict, scorer, summarize).
 *
 * @returns The finished call entry for reference
 */
async function createAndFinishCall(
  client: any,
  internalCall: InternalCall,
  opRef: any,
  params: any[],
  parameterNames: any,
  thisArg: any,
  currentEntry: CallStackEntry,
  parentEntry: CallStackEntry | undefined,
  startTime: Date,
  output: any,
  displayName?: string,
  attributes?: Record<string, any>
): Promise<CallStackEntry> {
  const startPromise = client.createCall(
    internalCall,
    opRef,
    params,
    parameterNames,
    thisArg,
    currentEntry,
    parentEntry,
    startTime,
    displayName,
    attributes
  );

  const endTime = new Date();
  await client.finishCall(
    internalCall,
    output,
    currentEntry,
    parentEntry,
    undefined,
    endTime,
    startPromise
  );

  return currentEntry;
}

// ============================================================================
// WeaveObject Classes (Internal)
// ============================================================================

/**
 * Evaluation WeaveObject for imperative evaluation logging.
 * Internal to evaluationLogger - not exported from main SDK.
 *
 * Named "Evaluation" so that constructor.name serializes to 'Evaluation'.
 */
interface EvaluationParameters extends WeaveObjectParameters {
  dataset?: Dataset<any> | string;
  scorers?: string[];
  [key: string]: any; // Allow arbitrary attributes (trial_id, run_id, etc.)
}

class Evaluation extends WeaveObject {
  dataset?: Dataset<any> | string;
  scorers: string[];

  constructor(parameters: EvaluationParameters) {
    super(parameters);
    this.dataset = parameters.dataset;
    this.scorers = parameters.scorers || [];

    // Copy any additional attributes (e.g., trial_id, run_id, experiment_name)
    // that weren't already handled above. These will be serialized as part of
    // the WeaveObject and visible in the Weave UI.
    // Exclude properties already explicitly assigned to avoid duplication.
    const excludedKeys = ['dataset', 'scorers', 'name', 'description'];
    for (const [key, value] of Object.entries(parameters)) {
      if (!excludedKeys.includes(key)) {
        (this as any)[key] = value;
      }
    }
  }
}

/**
 * Model WeaveObject for imperative evaluation logging.
 * Used when user doesn't provide a proper Model instance.
 *
 * Named "Model" so that constructor.name serializes to 'Model'.
 */
interface ModelParameters extends WeaveObjectParameters {
  modelName?: string;
  [key: string]: any;
}

class Model extends WeaveObject {
  modelName?: string;

  constructor(parameters: ModelParameters) {
    super(parameters);
    this.modelName = parameters.modelName;

    // Copy any additional attributes (e.g., model_version, provider, temperature)
    // that weren't already handled above. These will be serialized as part of
    // the WeaveObject and visible in the Weave UI.
    // Exclude properties already explicitly assigned to avoid duplication.
    const excludedKeys = ['modelName', 'name', 'description'];
    for (const [key, value] of Object.entries(parameters)) {
      if (!excludedKeys.includes(key)) {
        (this as any)[key] = value;
      }
    }
  }
}

/**
 * Scorer WeaveObject for imperative evaluation logging.
 * Named "Scorer" so that constructor.name serializes to 'Scorer'.
 */
interface ScorerParameters extends WeaveObjectParameters {
  scorerName?: string;
  [key: string]: any;
}

class Scorer extends WeaveObject {
  scorerName?: string;

  constructor(parameters: ScorerParameters) {
    super(parameters);
    this.scorerName = parameters.scorerName;

    // Copy any additional attributes (e.g., threshold, metric_type)
    // that weren't already handled above. These will be serialized as part of
    // the WeaveObject and visible in the Weave UI.
    // Exclude properties already explicitly assigned to avoid duplication.
    const excludedKeys = ['scorerName', 'name', 'description'];
    for (const [key, value] of Object.entries(parameters)) {
      if (!excludedKeys.includes(key)) {
        (this as any)[key] = value;
      }
    }
  }
}

// ============================================================================
// Built-in Ops (Internal)
// ============================================================================

/**
 * Built-in Ops for imperative evaluation.
 * These are internal SDK operations - not exported to users.
 * They are never executed; their purpose is to provide structure and source code
 * that gets captured and displayed in the Weave UI.
 */

const evaluationEvaluate = op(
  async function evaluate(evaluation: any, model: any): Promise<any> {
    // internal function
  },
  {name: 'Evaluation.evaluate'}
);

const evaluationPredictAndScore = op(
  async function predict_and_score(
    evaluation: any,
    model: any,
    example: Record<string, any>
  ): Promise<any> {
    // internal function
  },
  {name: 'Evaluation.predict_and_score'}
);

const evaluationSummarize = op(
  async function summarize(evaluation: any): Promise<any> {
    // internal function
  },
  {name: 'Evaluation.summarize'}
);

const modelPredict = op(
  async function predict(
    model: any,
    inputs: Record<string, any>
  ): Promise<any> {
    // internal function
  },
  {name: 'Model.predict'}
);

const scorerScoreFactory = (scorerName: string) =>
  op(
    async function score(scorer: any, output: any, target?: any): Promise<any> {
      // internal function
    },
    {name: `${scorerName}.score`}
  );

// ============================================================================
// Metadata Tracking
// ============================================================================

/**
 * Tracks metadata for a single prediction's predict_and_score call.
 * The predict call is finished immediately in logPrediction() to capture correct duration.
 * Scorer feedback is then attached to the finished predict call.
 */
interface PredictAndScoreCallMetadataOptions {
  predictAndScoreCall: InternalCall;
  predictAndScoreEntry: CallStackEntry;
  evaluateEntry: CallStackEntry;
  predictAndScoreStartPromise: Promise<any>;
  predictCallId: string;
  output: any;
}

class PredictAndScoreCallMetadata {
  predictAndScoreCall: InternalCall;
  predictAndScoreEntry: CallStackEntry;
  evaluateEntry: CallStackEntry;
  predictAndScoreStartPromise: Promise<any>;
  predictCallId: string; // ID of the finished predict call (for attaching feedback)
  scores: Record<string, any> = {};
  output: any;

  constructor(options: PredictAndScoreCallMetadataOptions) {
    this.predictAndScoreCall = options.predictAndScoreCall;
    this.predictAndScoreEntry = options.predictAndScoreEntry;
    this.evaluateEntry = options.evaluateEntry;
    this.predictAndScoreStartPromise = options.predictAndScoreStartPromise;
    this.predictCallId = options.predictCallId;
    this.output = options.output;
  }
}

/**
 * Incremental aggregates for summary calculation.
 * Instead of storing all predictions, we maintain running aggregates
 * to compute mean/true_fraction incrementally in O(1) memory.
 */
interface ScoreAggregate {
  count: number;
  sum?: number; // For numeric scores
  trueCount?: number; // For boolean scores
  type: 'number' | 'boolean' | 'mixed';
}

// ============================================================================
// ScoreLogger
// ============================================================================

/**
 * ScoreLogger manages scoring for a single prediction.
 * Returned from EvaluationLogger.logPrediction().
 *
 * @example
 * const pred = await ev.logPrediction(example, output);
 * await pred.logScore("accuracy", 0.95);
 * await pred.logScore("relevance", 0.8);
 * await pred.finish(); // Finalizes the prediction
 */
export class ScoreLogger {
  private predMeta?: PredictAndScoreCallMetadata;
  private evalLogger: EvaluationLogger;
  private operationChain: Promise<void> = Promise.resolve();
  private initPromise: Promise<void>;
  private initResolve?: () => void;
  private finishCalled: boolean = false;

  constructor(evalLogger: EvaluationLogger) {
    this.evalLogger = evalLogger;
    this.initPromise = new Promise<void>(resolve => {
      this.initResolve = resolve;
    });
  }

  /**
   * Initialize the ScoreLogger with metadata.
   * Called by EvaluationLogger after async initialization completes.
   * @internal
   */
  initialize(predMeta: PredictAndScoreCallMetadata): void {
    this.predMeta = predMeta;
    this.initResolve?.();
  }

  /**
   * Wait for all operations in this ScoreLogger to complete.
   * Used by EvaluationLogger to ensure all async operations finish before finalizing.
   * @internal
   */
  async waitForCompletion(): Promise<void> {
    await this.operationChain;
  }

  /**
   * Check if finish() has been called.
   * Used by EvaluationLogger to detect unfinished predictions.
   */
  get isFinishCalled(): boolean {
    return this.finishCalled;
  }

  /**
   * Log a score for this prediction.
   * Creates a scorer call as a child of predict_and_score.
   *
   * @param scorerName - Name of the scorer (e.g., "accuracy", "f1_score")
   * @param score - The score value
   */
  logScore(scorerName: string, score: any): Promise<void> {
    // Add operation to the chain
    const operation = this.operationChain
      .then(async () => {
        // Wait for initialization to complete
        await this.initPromise;

        if (!this.predMeta) {
          // ScoreLogger was not properly initialized, skip
          return;
        }

        const client = requireGlobalClient();

        // Dynamically create a Scorer class with the scorer name
        // Override the class name so constructor.name === scorerName for proper serialization
        class DynamicScorer extends Scorer {
          constructor(parameters: ScorerParameters) {
            super({
              ...parameters,
              name: scorerName,
              scorerName: scorerName,
            });
          }
        }

        // Override the constructor name to be the scorer name
        Object.defineProperty(DynamicScorer, 'name', {
          value: scorerName,
          writable: false,
          configurable: true,
        });

        // Create an instance of the dynamic scorer class
        const scorer = new DynamicScorer({});

        // Save the scorer to get its URI for feedback attachment
        const scorerRef = await client.publish(scorer);
        const scorerRefUri = scorerRef.uri();

        // Create and finish scorer call (already have the score)
        const scorerCall = new InternalCall();
        const scorerEntry: CallStackEntry = {
          callId: uuidv7(),
          traceId: this.predMeta.predictAndScoreEntry.traceId,
          childSummary: {},
        };

        await createAndFinishCall(
          client,
          scorerCall,
          scorerScoreFactory(scorerName),
          [{self: scorer, output: this.predMeta.output}],
          'useParam0Object',
          scorer,
          scorerEntry,
          this.predMeta.predictAndScoreEntry,
          new Date(),
          score,
          `${scorerName}.score`,
          IMPERATIVE_SCORE_MARKER
        );

        // Attach the score as feedback to the predict call
        await client.addScore(
          this.predMeta.predictCallId,
          scorerEntry.callId,
          scorerRefUri,
          score
        );

        // Store score in metadata
        this.predMeta.scores[scorerName] = score;
      })
      .catch(err => {
        // Log error but don't break the chain for other operations
        console.error(`Failed to log score ${scorerName}:`, err);
      });

    // Update the chain
    this.operationChain = operation;

    // Return the operation promise so caller can await if desired
    return operation;
  }

  /**
   * Finish the scoring process for the prediction.
   * Finalizes the predict_and_score call with accumulated scores.
   * Updates incremental aggregates and frees memory.
   */
  finish(): Promise<void> {
    if (this.finishCalled) {
      return Promise.resolve(); // Already finished
    }

    this.finishCalled = true;

    // Add finish operation to the chain
    const operation = this.operationChain.then(async () => {
      // Wait for initialization to complete
      await this.initPromise;

      if (!this.predMeta) {
        // ScoreLogger was not properly initialized, skip
        return;
      }

      const client = requireGlobalClient();
      const endTime = new Date();

      // Finish predict_and_score call with output and scores
      await client.finishCall(
        this.predMeta.predictAndScoreCall,
        {
          output: this.predMeta.output,
          scores: this.predMeta.scores,
        },
        this.predMeta.predictAndScoreEntry,
        this.predMeta.evaluateEntry, // Parent = evaluate
        undefined,
        endTime,
        this.predMeta.predictAndScoreStartPromise // Use saved startPromise
      );

      // Update incremental aggregates for summary calculation
      this.evalLogger.updateScoreAggregates(this.predMeta.scores);
    });

    // Update the chain
    this.operationChain = operation;

    // Return the operation promise so caller can await if desired
    return operation;
  }
}

// ============================================================================
// EvaluationLogger
// ============================================================================

/**
 * Options for creating an EvaluationLogger.
 */
export interface EvaluationLoggerOptions {
  name: string;
  description?: string;
  dataset?: Dataset<any> | string;
  scorers?: string[];
  model?: WeaveObject | {name?: string};
  attributes?: Record<string, any>; // Custom attributes to attach to evaluate call
  [key: string]: any; // Allow arbitrary attributes
}

/**
 * EvaluationLogger enables incremental logging of predictions and scores.
 *
 * Unlike the traditional Evaluation class which requires upfront dataset and batch processing,
 * EvaluationLogger allows you to log predictions as they happen, with flexible scoring.
 *
 * @example
 * const ev = new EvaluationLogger({name: 'my-eval', dataset: 'my-dataset'});
 *
 * for (const example of streamingData) {
 *   const output = await myModel.predict(example);
 *   const pred = ev.logPrediction(example, output);
 *
 *   if (shouldScore(output)) {
 *     pred.logScore("accuracy", calculateAccuracy(output));
 *   }
 *   pred.finish();
 * }
 *
 * await ev.logSummary();
 */
export class EvaluationLogger {
  private evaluation: Evaluation;
  private initPromise: Promise<void>;
  private model: Model | WeaveObject;
  private evalAttributes: Record<string, any>;

  // Evaluate call tracking
  private evaluateCall?: InternalCall;
  private evaluateEntry?: CallStackEntry;
  private evaluateStartPromise?: Promise<any>;

  // Incremental summary aggregates (O(K) memory where K = # scorers)
  private scoreAggregates: Map<string, ScoreAggregate> = new Map();

  // Track all ScoreLogger instances for coordination
  private scoreLoggers: Set<ScoreLogger> = new Set();

  private isFinalized: boolean = false;

  constructor(options: EvaluationLoggerOptions) {
    this.evalAttributes = options.attributes || {};
    // Create Evaluation WeaveObject
    this.evaluation = new Evaluation({
      name: options.name,
      description: options.description,
      dataset: options.dataset,
      scorers: options.scorers || [],
      // Copy any additional attributes
      ...Object.fromEntries(
        Object.entries(options).filter(
          ([key]) =>
            ![
              'name',
              'description',
              'dataset',
              'scorers',
              'model',
              'attributes',
            ].includes(key)
        )
      ),
    });

    // Wrap model if it's not already a WeaveObject
    if (options.model instanceof WeaveObject) {
      this.model = options.model;
    } else {
      this.model = new Model({
        name: options.model?.name || 'model',
        modelName: options.model?.name,
      });
    }

    // Start the evaluate call
    this.initPromise = this.startEvaluate();
  }

  /**
   * Start the evaluate call (root of the call hierarchy).
   */
  private async startEvaluate(): Promise<void> {
    const client = requireGlobalClient();

    // Create evaluate call
    const evaluateCall = new InternalCall();
    const evaluateEntry: CallStackEntry = {
      callId: uuidv7(),
      traceId: uuidv7(), // Root call gets new trace ID
      childSummary: {},
    };

    const startTime = new Date();
    const evaluateStartPromise = client.createCall(
      evaluateCall,
      evaluationEvaluate,
      [{self: this.evaluation, model: this.model}],
      'useParam0Object',
      undefined,
      evaluateEntry,
      undefined, // No parent (root call)
      startTime,
      undefined, // displayName
      {...IMPERATIVE_EVAL_MARKER, ...this.evalAttributes} // Merge eval attributes
    );
    await evaluateStartPromise;

    this.evaluateCall = evaluateCall;
    this.evaluateEntry = evaluateEntry;
    this.evaluateStartPromise = evaluateStartPromise;
  }

  /**
   * Log a prediction with its input and output (synchronous version).
   * Creates a predict_and_score call (with child predict call).
   * Returns a ScoreLogger immediately for adding scores.
   *
   * This method returns the ScoreLogger synchronously. Operations on the
   * ScoreLogger (logScore, finish) will be queued and executed when initialization completes.
   *
   * @example
   * // Fire-and-forget style
   * const scoreLogger = evalLogger.logPrediction({input: 'test'}, 'output');
   * scoreLogger.logScore('accuracy', 0.95);
   * scoreLogger.finish();
   * await evalLogger.logSummary(); // Waits for everything
   */
  logPrediction(inputs: Record<string, any>, output: any): ScoreLogger {
    // Create ScoreLogger immediately (synchronously)
    const scoreLogger = new ScoreLogger(this);
    this.scoreLoggers.add(scoreLogger);

    // Start async initialization in the background
    this.logPredictionImpl(inputs, output, scoreLogger);

    // Return scoreLogger immediately
    return scoreLogger;
  }

  /**
   * Log a prediction with its input and output (async version).
   * Like logPrediction() but returns a Promise that resolves when
   * the prediction call is fully initialized.
   *
   * Use this if you need to await the initialization before proceeding.
   *
   * @example
   * // Awaitable style
   * const scoreLogger = await evalLogger.logPredictionAsync({input: 'test'}, 'output');
   * await scoreLogger.logScore('accuracy', 0.95);
   * await scoreLogger.finish();
   */
  async logPredictionAsync(
    inputs: Record<string, any>,
    output: any
  ): Promise<ScoreLogger> {
    // Create ScoreLogger immediately (synchronously)
    const scoreLogger = new ScoreLogger(this);
    this.scoreLoggers.add(scoreLogger);

    // Wait for async initialization to complete
    await this.logPredictionImpl(inputs, output, scoreLogger);

    // Return initialized scoreLogger
    return scoreLogger;
  }

  /**
   * Internal implementation of logPrediction.
   * Performs async initialization and sets up the prediction call tree.
   */
  private async logPredictionImpl(
    inputs: Record<string, any>,
    output: any,
    scoreLogger: ScoreLogger
  ): Promise<void> {
    await this.initPromise;
    const client = requireGlobalClient();
    if (!client || !this.evaluateEntry) {
      console.warn('Weave not initialized or evaluate not started');
      // ScoreLogger will remain uninitialized and operations will be no-ops
      return;
    }

    // Create predict_and_score call
    const predictAndScoreCall = new InternalCall();
    const predictAndScoreEntry: CallStackEntry = {
      callId: uuidv7(),
      traceId: this.evaluateEntry!.traceId,
      childSummary: {},
    };

    const startTime = new Date();
    const predictAndScoreStartPromise = client.createCall(
      predictAndScoreCall,
      evaluationPredictAndScore,
      [{self: this.evaluation, model: this.model, example: inputs}],
      'useParam0Object',
      undefined,
      predictAndScoreEntry,
      this.evaluateEntry!, // Parent = evaluate
      startTime,
      undefined, // displayName
      IMPERATIVE_EVAL_MARKER // attributes
    );

    await predictAndScoreStartPromise;

    // Create predict call
    const predictCall = new InternalCall();
    const predictEntry: CallStackEntry = {
      callId: uuidv7(),
      traceId: this.evaluateEntry!.traceId,
      childSummary: {},
    };

    // Create and finish predict call (already have the output)
    await createAndFinishCall(
      client,
      predictCall,
      modelPredict,
      [inputs],
      undefined,
      undefined,
      predictEntry,
      predictAndScoreEntry,
      startTime,
      output,
      undefined,
      IMPERATIVE_EVAL_MARKER
    );

    // Store metadata (predict call already finished, only track predict_and_score)
    const predMeta = new PredictAndScoreCallMetadata({
      predictAndScoreCall,
      predictAndScoreEntry,
      evaluateEntry: this.evaluateEntry!,
      predictAndScoreStartPromise,
      predictCallId: predictEntry.callId,
      output,
    });

    // Initialize the scoreLogger with metadata
    scoreLogger.initialize(predMeta);
  }

  /**
   * Log a summary and finalize the evaluation.
   * Creates a summarize call and finishes the evaluate call.
   *
   * This method can be called without await (fire-and-forget), but internally
   * it will wait for all pending operations to complete.
   */
  async logSummary(summary?: Record<string, any>): Promise<void> {
    await this.initPromise;
    const client = requireGlobalClient();
    if (!client || !this.evaluateEntry) {
      console.warn('Weave not initialized or evaluate not started');
      return;
    }

    if (this.isFinalized) {
      return; // Already finalized
    }

    // Check for unfinished predictions and auto-finish them
    const unfinishedScoreLoggers = Array.from(this.scoreLoggers).filter(
      sl => !sl.isFinishCalled
    );

    if (unfinishedScoreLoggers.length > 0) {
      console.warn(
        `logSummary() called with ${unfinishedScoreLoggers.length} unfinished prediction(s). ` +
          `Auto-finishing them now...`
      );
      // Auto-finish all unfinished score loggers
      unfinishedScoreLoggers.forEach(sl => sl.finish());
    }

    // Wait for all score loggers to complete their operations
    await Promise.all(
      Array.from(this.scoreLoggers).map(sl => sl.waitForCompletion())
    );

    // Auto-generate summary if not provided
    if (!summary) {
      summary = this.generateAutoSummary();
    }

    // Create and finish summarize call (already have the summary)
    const summarizeCall = new InternalCall();
    const summarizeEntry: CallStackEntry = {
      callId: uuidv7(),
      traceId: this.evaluateEntry!.traceId,
      childSummary: {},
    };

    await createAndFinishCall(
      client,
      summarizeCall,
      evaluationSummarize,
      [{self: this.evaluation}],
      'useParam0Object',
      undefined,
      summarizeEntry,
      this.evaluateEntry!,
      new Date(),
      summary,
      undefined,
      IMPERATIVE_EVAL_MARKER
    );

    // Finish evaluate call with summary
    await client.finishCall(
      this.evaluateCall!,
      summary,
      this.evaluateEntry!,
      undefined, // No parent
      undefined,
      new Date(),
      this.evaluateStartPromise! // Use saved startPromise
    );

    this.isFinalized = true;
  }

  /**
   * Update incremental aggregates when a prediction is finished.
   * Called by ScoreLogger.finish() to maintain O(1) memory usage.
   * @internal
   */
  updateScoreAggregates(scores: Record<string, any>): void {
    for (const [scoreName, score] of Object.entries(scores)) {
      if (score == null) continue;

      let agg = this.scoreAggregates.get(scoreName);

      if (!agg) {
        // Initialize aggregate based on first value type
        const type =
          typeof score === 'number'
            ? 'number'
            : typeof score === 'boolean'
              ? 'boolean'
              : 'mixed';
        agg = {count: 0, type};
        if (type === 'number') agg.sum = 0;
        if (type === 'boolean') agg.trueCount = 0;
        this.scoreAggregates.set(scoreName, agg);
      }

      // Update aggregate
      agg.count++;
      if (agg.type === 'number' && typeof score === 'number') {
        agg.sum! += score;
      } else if (agg.type === 'boolean' && typeof score === 'boolean') {
        if (score) agg.trueCount!++;
      } else if (typeof score !== agg.type) {
        // Mixed types - can't aggregate
        agg.type = 'mixed';
      }
    }
  }

  /**
   * Generate auto-summary from incremental aggregates.
   * Calculates mean for numeric scores, true_fraction for boolean scores.
   * Runs in O(K) time where K = number of unique scorers.
   */
  private generateAutoSummary(): Record<string, any> {
    const summary: Record<string, any> = {};

    for (const [scoreName, agg] of this.scoreAggregates) {
      if (agg.count === 0) continue;

      if (agg.type === 'number') {
        summary[scoreName] = {
          mean: agg.sum! / agg.count,
        };
      } else if (agg.type === 'boolean') {
        summary[scoreName] = {
          true_count: agg.trueCount!,
          true_fraction: agg.trueCount! / agg.count,
        };
      }
      // Skip 'mixed' type - can't compute meaningful aggregate
    }

    return summary;
  }
}
