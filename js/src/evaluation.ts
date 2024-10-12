import { WeaveObject, WeaveObjectParameters } from "./weaveObject";
import { Op, getOpName } from "./opType";
import { boundOp } from "./op";
import { Dataset } from "./dataset";
import { isMedia } from "./media";
import { DatasetRow } from "./dataset";
import cliProgress from "cli-progress";

const PROGRESS_BAR = false;

interface EvaluationParameters<R extends DatasetRow, M>
  extends WeaveObjectParameters {
  dataset: Dataset<R>;
  scorers: WeaveCallable<
    (...args: [{ datasetRow: R; modelOutput: M }]) => any
  >[];
  maxConcurrency?: number;
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
  if (typeof callable === "function") {
    return callable(...args);
  }
  return callable.invoke(...args);
}

function weaveCallableName<T extends (...args: any[]) => any>(
  callable: WeaveCallable<T>
) {
  if (typeof callable === "function") {
    return getOpName(callable);
  }
  return callable.id;
}

async function* repeatAsyncIterator<T>(
  asyncIterator: AsyncIterable<T>,
  repeatCount: number
): AsyncGenerator<T, void, unknown> {
  for (let i = 0; i < repeatCount; i++) {
    for await (const item of asyncIterator) {
      yield item;
    }
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
    Promise<{ item: T; result: Awaited<U> }>
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

export class Evaluation<R extends DatasetRow, M> extends WeaveObject {
  private dataset: Dataset<R>;
  private scorers: WeaveCallable<
    (...args: [{ datasetRow: R; modelOutput: M }]) => any
  >[];

  constructor(parameters: EvaluationParameters<R, M>) {
    super(parameters);
    this.dataset = parameters.dataset;
    this.scorers = parameters.scorers;
    this.evaluate = boundOp(this, this.evaluate, {
      parameterNames: "useParam0Object",
      callDisplayName: (inputs) =>
        `${this.id}_${weaveCallableName(inputs.model)}`,
    });
    this.predict_and_score = boundOp(this, this.predict_and_score, {
      parameterNames: "useParam0Object",
    });
  }

  async evaluate({
    model,
    nTrials = 1,
    maxConcurrency = 5,
  }: {
    model: WeaveCallable<(...args: [{ datasetRow: R }]) => Promise<M>>;
    nTrials?: number;
    maxConcurrency?: number;
  }) {
    const results: Array<{
      model_output: any;
      model_success: boolean;
      model_latency: number;
      [key: string]: any;
    }> = [];

    const progressBar = new cliProgress.SingleBar({
      format:
        "Evaluating |{bar}| {percentage}% | ETA: {eta}s | {modelErrors} errors | {value}/{total} examples | {running} running",
      barCompleteChar: "\u2588",
      barIncompleteChar: "\u2591",
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

    // for await (const { result, nRunning, nDone } of asyncParallelMap(
    for await (const { result, nRunning, nDone } of asyncParallelMap(
      datasetExamples,
      this.predict_and_score,
      (item) => [{ model, example: item }],
      maxConcurrency
    )) {
      const { scores } = result;
      results.push({
        model_success: result.model_success,
        model_output: result.model_output,
        ...scores,
        model_latency: result.model_latency,
      });
      modelErrors += result.model_success ? 0 : 1;
      if (PROGRESS_BAR) {
        progressBar.update(nDone, { running: nRunning, modelErrors });
      } else {
        console.log(
          `Evaluating ${nDone}/${
            this.dataset.length * nTrials
          } examples (${nRunning} running, ${modelErrors} errors)`
        );
      }
    }

    if (PROGRESS_BAR) {
      progressBar.stop();
    }

    return this.summarizeResults(results);
  }

  async predict_and_score({
    model,
    example,
  }: {
    model: WeaveCallable<(...args: [{ datasetRow: R }]) => Promise<M>>;
    example: R;
  }) {
    const startTime = new Date();
    let modelOutput;
    let modelError = false;
    try {
      modelOutput = await callWeaveCallable(model, { datasetRow: example });
    } catch (e) {
      console.error(e);
      modelError = true;
    }
    const endTime = new Date();
    const modelLatency = (endTime.getTime() - startTime.getTime()) / 1000; // Convert to seconds

    const scores: { [key: string]: any } = {};
    if (!modelError) {
      for (const scorer of this.scorers) {
        try {
          const score = await callWeaveCallable(scorer, {
            datasetRow: example,
            modelOutput,
          });
          scores[weaveCallableName(scorer)] = score;
        } catch (e) {
          console.error(e);
          scores[getOpName(scorer)] = undefined;
        }
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
      const allKeys = new Set(results.flatMap((obj) => Object.keys(obj ?? {})));

      for (const key of allKeys) {
        const values = results.map((result) =>
          result == null ? null : result[key]
        );
        if (
          values.some(
            (v) =>
              typeof v === "object" &&
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
    const nonNilValues = values.filter((v) => v != null);
    if (nonNilValues.length === 0) {
      return {}; // Return an empty object if there are no valid values
    }

    if (nonNilValues.every((v) => typeof v === "boolean")) {
      const trueCount = nonNilValues.filter((v) => v).length;
      return {
        true_count: trueCount,
        true_fraction: values.length > 0 ? trueCount / values.length : 0,
      };
    } else if (nonNilValues.every((v) => typeof v === "number")) {
      const sum = nonNilValues.reduce((acc, v) => acc + v, 0);
      return {
        mean: values.length > 0 ? sum / values.length : 0,
      };
    }
    return {};
  }
}
