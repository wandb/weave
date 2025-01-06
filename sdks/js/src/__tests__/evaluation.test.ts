import {Dataset} from '../dataset';
import {Evaluation} from '../evaluation';
import {ColumnMapping} from '../fn';
import {op} from '../op';

const createMockDataset = () =>
  new Dataset({
    rows: [
      {id: 0, text: 'Example 0'},
      {id: 1, text: 'Example 1'},
      {id: 2, text: 'Example 2'},
      {id: 3, text: 'Example 3'},
      {id: 4, text: 'Example 4'},
    ],
  });

const createMockDatasetWithDifferentColumnNames = () =>
  new Dataset({
    rows: [
      {identifier: 0, description: 'Example 0'},
      {identifier: 1, description: 'Example 1'},
      {identifier: 2, description: 'Example 2'},
      {identifier: 3, description: 'Example 3'},
      {identifier: 4, description: 'Example 4'},
    ],
  });

const createMockModel = (failable: boolean) => {
  return op(async function mockPrediction({
    datasetRow,
  }: {
    datasetRow: {id: number; text: string};
  }) {
    if (failable && datasetRow.id === 0) throw new Error('Model failed');
    if (failable && datasetRow.text === undefined)
      throw new Error('Model failed');
    return `Prediction for ${datasetRow.text}`;
  });
};

const createMockScorers = (failable: boolean) => {
  return [
    op(async function lengthScorer({
      datasetRow,
      modelOutput,
    }: {
      datasetRow: {id: number; text: string};
      modelOutput: string;
    }) {
      if (failable && datasetRow.id === 3) throw new Error('Scorer 1 failed');
      return {
        explanation: 'length is ' + modelOutput.length,
        length: modelOutput.length,
      };
    }),
    op(async function inclusionScorer({
      modelOutput,
      datasetRow,
    }: {
      modelOutput: string;
      datasetRow: {id: number; text: string};
    }) {
      return modelOutput.includes(datasetRow.text);
    }),
  ];
};

const createMockEvaluation = (
  failable: boolean,
  dataset: Dataset<any> = createMockDataset(),
  columnMapping?: ColumnMapping<any, any>
) => {
  return new Evaluation({
    dataset,
    scorers: createMockScorers(failable),
    columnMapping,
  });
};

describe('Evaluation', () => {
  test('summarizeResults', async () => {
    const mockEval = createMockEvaluation(false);
    const mockModel = createMockModel(false);

    const results = await mockEval.evaluate({model: mockModel});
    const expectedResults = {
      model_success: {true_count: 5, true_fraction: 1},
      inclusionScorer: {
        true_count: 5,
        true_fraction: 1,
      },
      lengthScorer: {
        length: {
          mean: 24,
        },
      },
      model_latency: {mean: expect.any(Number)},
    };

    expect(results).toEqual(expectedResults);
  });
  test('summarizeResults with failed predictions and scorers', async () => {
    const mockEval = createMockEvaluation(true);
    const mockModel = createMockModel(true);

    const results = await mockEval.evaluate({model: mockModel});
    const expectedResults = {
      model_success: {true_count: 4, true_fraction: 0.8},
      inclusionScorer: {
        true_count: 4,
        true_fraction: 0.8,
      },
      lengthScorer: {
        length: {
          mean: 14.4,
        },
      },
      model_latency: {mean: expect.any(Number)},
    };

    expect(results).toEqual(expectedResults);
  });

  test('evaluate with a valid column mapping', async () => {
    const mockEval = createMockEvaluation(
      true,
      createMockDatasetWithDifferentColumnNames(),
      {
        id: 'identifier',
        text: 'description',
      }
    );
    const mockModel = createMockModel(true);
    const res = await mockEval.evaluate({model: mockModel});
    expect(res).toEqual({
      model_success: {
        true_count: 4,
        true_fraction: 0.8,
      },
      inclusionScorer: {
        true_count: 4,
        true_fraction: 0.8,
      },
      lengthScorer: {
        length: {
          mean: 14.4,
        },
      },
      model_latency: {mean: expect.any(Number)},
    });
  });

  test('evaluate with an invalid column mapping', async () => {
    // These cols dont map as expected, so the model should fail
    const mockEval = createMockEvaluation(
      true,
      createMockDatasetWithDifferentColumnNames(),
      {
        id: 'totallyNot',
        text: 'validMapping',
      }
    );
    const mockModel = createMockModel(true);

    const res = await mockEval.evaluate({model: mockModel});
    expect(res).toEqual({
      model_success: {true_count: 0, true_fraction: 0},
      model_latency: {mean: expect.any(Number)},
    });
  });
});
