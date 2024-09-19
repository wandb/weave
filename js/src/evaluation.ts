import { WeaveObject, WeaveObjectParameters } from "./weaveObject";
import { Op, getOpName } from "./opType";
import { boundOp } from "./op";
import { Dataset } from "./dataset";
import { isMedia } from "./media";
import cliProgress from "cli-progress";

interface EvaluationParameters extends WeaveObjectParameters {
  dataset: Dataset;
  scorers: Op<any>[];
  maxConcurrency?: number;
}

interface Runnable {
  run: (...args: any[]) => Promise<any>;
}

type WeaveCallable = Op<any> | Runnable;

function callWeaveCallable(callable: WeaveCallable, ...args: any[]) {
  if (typeof callable === "function") {
    return callable(...args);
  }
  return callable.run(...args);
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

export class Evaluation extends WeaveObject {
  private dataset: Dataset;
  private scorers: Op<any>[];

  constructor(parameters: EvaluationParameters) {
    super(parameters);
    this.dataset = parameters.dataset;
    this.scorers = parameters.scorers;
    this.evaluate = boundOp(this, this.evaluate, {
      parameterNames: "useParam0Object",
    });
    this.predict_and_score = boundOp(this, this.predict_and_score, {
      parameterNames: "useParam0Object",
    });
  }

  async evaluate({
    model,
    maxConcurrency = 5,
  }: {
    model: WeaveCallable;
    maxConcurrency?: number;
  }) {
    const results: Array<{
      modelOutput: any;
      modelError: number;
      modelLatency: number;
      [key: string]: any;
    }> = [];

    const progressBar = new cliProgress.SingleBar({
      format:
        "Evaluating |{bar}| {percentage}% | ETA: {eta}s | {modelErrors} errors | {value}/{total} examples | {running} running",
      barCompleteChar: "\u2588",
      barIncompleteChar: "\u2591",
      hideCursor: true,
    });

    progressBar.start(this.dataset.length, 0, {
      running: 0,
      modelErrors: 0,
    });

    let modelErrors = 0;
    for await (const { result, nRunning, nDone } of asyncParallelMap(
      this.dataset,
      this.predict_and_score,
      (item) => [{ model, example: item }],
      maxConcurrency
    )) {
      const { scores, ...rest } = result;
      results.push({ ...rest, ...scores });
      modelErrors += result.modelError;
      progressBar.update(nDone, { running: nRunning, modelErrors });
    }

    progressBar.stop();

    return this.summarizeResults(results);
  }

  async predict_and_score({
    model,
    example,
  }: {
    model: WeaveCallable;
    example: Record<string, any>;
  }) {
    const startTime = new Date();
    let modelOutput;
    let modelError = 0;
    try {
      modelOutput = await callWeaveCallable(model, example);
    } catch (e) {
      console.error(e);
      modelError = 1;
    }
    const endTime = new Date();
    const modelLatency = (endTime.getTime() - startTime.getTime()) / 1000; // Convert to seconds

    const scores: { [key: string]: any } = {};
    if (!modelError) {
      for (const scorer of this.scorers) {
        try {
          const score = await scorer(modelOutput, example);
          scores[getOpName(scorer)] = score;
        } catch (e) {
          console.error(e);
          scores[getOpName(scorer)] = undefined;
        }
      }
    }

    return { modelOutput, scores, modelLatency, modelError };
  }

  private summarizeResults(
    results: Array<{
      modelOutput: any;
      modelError: number;
      modelLatency: number;
      [key: string]: any;
    }>
  ) {
    const summarizeNestedObject = (
      obj: any,
      currentPath: string = ""
    ): Record<string, any> => {
      const nestedSummary: Record<string, any> = {};

      for (const [key, value] of Object.entries(obj)) {
        const newPath = currentPath ? `${currentPath}.${key}` : key;

        if (
          typeof value === "object" &&
          value !== null &&
          !Array.isArray(value) &&
          !isMedia(value)
        ) {
          nestedSummary[key] = summarizeNestedObject(value, newPath);
        } else {
          const values = results.map((result) => {
            const keys = newPath.split(".");
            return keys.reduce((acc: any, k) => acc && acc[k], result);
          });
          // Don't filter out undefined values?
          // .filter((v) => v !== undefined);

          const columnSummary = this.summarizeColumn(values);
          if (Object.keys(columnSummary).length > 0) {
            nestedSummary[key] = columnSummary;
          }
        }
      }

      return nestedSummary;
    };

    // Find the first result with valid scores to use as a template
    const templateResult =
      results.find((r) => r.modelError === 0) || results[0];
    return summarizeNestedObject(templateResult);
  }

  private summarizeColumn(values: any[]): Record<string, number> {
    const nonUndefinedValues = values.filter((v) => v !== undefined);
    if (nonUndefinedValues.length === 0) {
      return {}; // Return an empty object if there are no valid values
    }

    if (nonUndefinedValues.every((v) => typeof v === "boolean")) {
      const trueCount = nonUndefinedValues.filter((v) => v).length;
      return {
        true_count: trueCount,
        true_fraction: values.length > 0 ? trueCount / values.length : 0,
      };
    } else if (nonUndefinedValues.every((v) => typeof v === "number")) {
      const sum = nonUndefinedValues.reduce((acc, v) => acc + v, 0);
      return {
        mean: values.length > 0 ? sum / values.length : 0,
      };
    }
    return {};
  }
}
