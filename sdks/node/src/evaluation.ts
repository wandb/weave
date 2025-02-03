import cliProgress from 'cli-progress';
import {Dataset, DatasetRow} from './dataset';
import {ColumnMapping, mapArgs} from './fn';
import {isMedia} from './media';
import {op} from './op';
import {Op, getOpName} from './opType';
import {WeaveObject, WeaveObjectParameters} from './weaveObject';

const PROGRESS_BAR = false;

// Column mapping takes a dataset row of type R and maps it to a scorer's dataset row of type E
interface EvaluationParameters<R extends DatasetRow, E extends DatasetRow, M>
  extends WeaveObjectParameters {
  dataset: Dataset<R>;
  scorers: WeaveCallable<(...args: [{datasetRow: E; modelOutput: M}]) => any>[];
  maxConcurrency?: number;
  columnMapping?: ColumnMapping<R, E>;
}

interface Runnable<T extends (...args: any[]) => any> {
  id: string;
  invoke: (...args: Parameters<T>) => ReturnType<T>;
}

type WeaveCallable<T extends (...args: any[]) => any> = Op<T> | Runnable<T>;

function callWeaveCallable<T extends (...args: any[]) => any>(
  callable: WeaveCallable<T>,
  ...args: Parameters<T>
) {
  if (typeof callable === 'function') {
    return callable(...args);
  }
  return callable.invoke(...args);
}

function weaveCallableName<T extends (...args: any[]) => any>(
  callable: WeaveCallable<T>
) {
  if (typeof callable === 'function') {
    return getOpName(callable);
  }
  return callable.id;
}

async function* repeatAsyncIterator<T>(
  asyncIterator: AsyncIterable<T>,
  repeatCount: number
) {
  for (let i = 0; i < repeatCount; i++) {
    yield* asyncIterator;
  }
}

async function* asyncParallelMap<T, U>(
  asyncIterator: AsyncIterable<T>,
  fn: (item: T, ...args: any[]) => Promise<U>,
  fnParams: (item: T) => any[],
  maxConcurrency: number
) {
  const itemPromiseMap: Map<
    T,
    Promise<{item: T; result: Awaited<U>}>
  > = new Map();
  async function runOne(item: T) {
    return {
      item,
      // @ts-ignore
      result: await fn(...fnParams(item)),
    };
  }
  let nDone = 0;
  for await (const item of asyncIterator) {
    if (itemPromiseMap.size >= maxConcurrency) {
      const done = await Promise.race(itemPromiseMap.values());
      itemPromiseMap.delete(done.item);
      yield {
        ...done,
        nRunning: itemPromiseMap.size,
        nDone: ++nDone,
      };
    }
    const prom = runOne(item);
    itemPromiseMap.set(item, prom);
  }

  // Flush remaining items
  while (itemPromiseMap.size > 0) {
    const done = await Promise.race(itemPromiseMap.values());
    itemPromiseMap.delete(done.item);
    yield {
      ...done,
      nRunning: itemPromiseMap.size,
      nDone: ++nDone,
    };
  }
}

/**
 * Sets up an evaluation which includes a set of scorers and a dataset.
 *
 * Calling evaluation.evaluate(model) will pass in rows form a dataset into a model matching
 * the names of the columns of the dataset to the argument names in model.predict.
 *
 * Then it will call all of the scorers and save the results in weave.
 *
 * @example
 * // Collect your examples into a dataset
 * const dataset = new weave.Dataset({
 *   id: 'my-dataset',
 *   rows: [
 *     { question: 'What is the capital of France?', expected: 'Paris' },
 *     { question: 'Who wrote "To Kill a Mockingbird"?', expected: 'Harper Lee' },
 *     { question: 'What is the square root of 64?', expected: '8' },
 *   ],
 * });
 *
 * // Define any custom scoring function
 * const scoringFunction = weave.op(function isEqual({ modelOutput, datasetRow }) {
 *   return modelOutput == datasetRow.expected;
 * });
 *
 * // Define the function to evaluate
 * const model = weave.op(async function alwaysParisModel({ question }) {
 *   return 'Paris';
 * });
 *
 * // Start evaluating
 * const evaluation = new weave.Evaluation({
 *   id: 'my-evaluation',
 *   dataset: dataset,
 *   scorers: [scoringFunction],
 * });
 *
 * const results = await evaluation.evaluate({ model });
 */
export class Evaluation<
  R extends DatasetRow,
  E extends DatasetRow,
  M,
> extends WeaveObject {
  private dataset: Dataset<R>;
  private scorers: WeaveCallable<
    (...args: [{datasetRow: E; modelOutput: M}]) => any
  >[];
  private columnMapping?: ColumnMapping<R, E>;

  constructor(parameters: EvaluationParameters<R, E, M>) {
    super(parameters);
    this.dataset = parameters.dataset;
    this.scorers = parameters.scorers;
    this.evaluate = op(this, this.evaluate, {
      parameterNames: 'useParam0Object',
      callDisplayName: inputs =>
        `${this.id}_${weaveCallableName(inputs.model)}`,
    });
    this.predictAndScore = op(this, this.predictAndScore, {
      parameterNames: 'useParam0Object',
    });
    this.columnMapping = parameters.columnMapping;
  }

  async evaluate({
    model,
    nTrials = 1,
    maxConcurrency = 5,
  }: {
    model: WeaveCallable<(...args: [{datasetRow: R}]) => Promise<M>>;
    nTrials?: number;
    maxConcurrency?: number;
  }) {
    const results: Array<{
      model_output: M;
      model_success: boolean;
      model_latency: number;
      [key: string]: any;
    }> = [];

    const progressBar = new cliProgress.SingleBar({
      format:
        'Evaluating |{bar}| {percentage}% | ETA: {eta}s | {modelErrors} errors | {value}/{total} examples | {running} running',
      barCompleteChar: '\u2588',
      barIncompleteChar: '\u2591',
      hideCursor: true,
    });

    if (PROGRESS_BAR) {
      progressBar.start(this.dataset.length * nTrials, 0, {
        running: 0,
        modelErrors: 0,
      });
    }

    let modelErrors = 0;
    let datasetExamples = this.dataset;
    if (nTrials > 1) {
      // @ts-ignore
      datasetExamples = repeatAsyncIterator(this.dataset, nTrials);
    }

    for await (const {result, nRunning, nDone} of asyncParallelMap(
      datasetExamples,
      this.predictAndScore,
      item => [{model, example: item, columnMapping: this.columnMapping}],
      maxConcurrency
    )) {
      const {scores} = result;
      results.push({
        model_success: result.model_success,
        model_output: result.model_output,
        ...scores,
        model_latency: result.model_latency,
      });
      modelErrors += result.model_success ? 0 : 1;
      if (PROGRESS_BAR) {
        progressBar.update(nDone, {running: nRunning, modelErrors});
      } else {
        console.log(
          `Evaluating ${nDone}/${this.dataset.length * nTrials} examples (${nRunning} running, ${modelErrors} errors)`
        );
      }
    }

    if (PROGRESS_BAR) {
      progressBar.stop();
    }

    return this.summarizeResults(results);
  }

  async predictAndScore({
    model,
    example,
    columnMapping,
  }: {
    model: WeaveCallable<(...args: [{datasetRow: E}]) => Promise<M>>;
    example: R;
    columnMapping?: ColumnMapping<R, E>;
  }) {
    const startTime = new Date();
    let modelOutput;
    let modelError = false;
    let datasetRow: E = example as unknown as E;
    if (columnMapping) {
      datasetRow = mapArgs(example, columnMapping) as E;
    }
    try {
      modelOutput = await callWeaveCallable(model, {datasetRow});
    } catch (e) {
      console.error(e);
      modelError = true;
    }
    const endTime = new Date();
    const modelLatency = (endTime.getTime() - startTime.getTime()) / 1000; // Convert to seconds

    const scores: {[key: string]: any} = {};
    if (!modelError) {
      for (const scorer of this.scorers) {
        let score = undefined;
        try {
          score = await callWeaveCallable(scorer, {datasetRow, modelOutput});
        } catch (e) {
          console.error(e);
        }
        scores[weaveCallableName(scorer)] = score;
      }
    }

    return {
      model_success: !modelError,
      model_output: modelOutput,
      scores,
      model_latency: modelLatency,
    };
  }

  private summarizeResults(
    results: Array<{
      model_output: any;
      model_success: boolean;
      model_latency: number;
      [key: string]: any;
    }>
  ) {
    const summarizeNestedObject = (
      results: Array<any>
    ): Record<string, any> => {
      const nestedSummary: Record<string, any> = {};

      // Get all unique keys from all results
      const allKeys = new Set(results.flatMap(obj => Object.keys(obj ?? {})));

      for (const key of allKeys) {
        const values = results.map(result =>
          result == null ? null : result[key]
        );
        if (
          values.some(
            v =>
              typeof v === 'object' &&
              v !== null &&
              !Array.isArray(v) &&
              !isMedia(v)
          )
        ) {
          const result = summarizeNestedObject(values);
          if (Object.keys(result).length > 0) {
            nestedSummary[key] = result;
          }
        } else {
          const columnSummary = this.summarizeColumn(values);
          if (Object.keys(columnSummary).length > 0) {
            nestedSummary[key] = columnSummary;
          }
        }
      }

      return nestedSummary;
    };

    return summarizeNestedObject(results);
  }

  private summarizeColumn(values: any[]): Record<string, number> {
    const nonNilValues = values.filter(v => v != null);
    if (nonNilValues.length === 0) {
      return {}; // Return an empty object if there are no valid values
    }

    if (nonNilValues.every(v => typeof v === 'boolean')) {
      const trueCount = nonNilValues.filter(v => v).length;
      return {
        true_count: trueCount,
        true_fraction: values.length > 0 ? trueCount / values.length : 0,
      };
    } else if (nonNilValues.every(v => typeof v === 'number')) {
      const sum = nonNilValues.reduce((acc, v) => acc + v, 0);
      return {
        mean: values.length > 0 ? sum / values.length : 0,
      };
    }
    return {};
  }
}
