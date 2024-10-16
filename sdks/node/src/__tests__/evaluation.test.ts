import { Dataset } from '../dataset';
import { Evaluation } from '../evaluation';
import { op } from '../op';

const createMockDataset = () =>
  new Dataset({
    rows: [
      { id: 0, text: 'Example 0' },
      { id: 1, text: 'Example 1' },
      { id: 2, text: 'Example 2' },
      { id: 3, text: 'Example 3' },
      { id: 4, text: 'Example 4' },
    ],
  });

const createMockModel = (failable: boolean) => {
  return op(async function mockPrediction({ datasetRow }: { datasetRow: { id: number; text: string } }) {
    if (failable && datasetRow.id === 0) throw new Error('Model failed');
    return `Prediction for ${datasetRow.text}`;
  });
};

const createMockScorers = (failable: boolean) => {
  return [
    op(async function lengthScorer({
      datasetRow,
      modelOutput,
    }: {
      datasetRow: { id: number; text: string };
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
      datasetRow: { id: number; text: string };
    }) {
      return modelOutput.includes(datasetRow.text);
    }),
  ];
};

const createMockEvaluation = (failable: boolean) => {
  return new Evaluation({
    dataset: createMockDataset(),
    scorers: createMockScorers(failable),
  });
};

describe('Evaluation', () => {
  test('summarizeResults', async () => {
    const mockEval = createMockEvaluation(false);
    const mockModel = createMockModel(false);

    const results = await mockEval.evaluate({ model: mockModel });
    const expectedResults = {
      model_success: { true_count: 5, true_fraction: 1 },
      inclusionScorer: {
        true_count: 5,
        true_fraction: 1,
      },
      lengthScorer: {
        length: {
          mean: 24,
        },
      },
      model_latency: { mean: expect.any(Number) },
    };

    expect(results).toEqual(expectedResults);
  });
  test('summarizeResults with failed predictions and scorers', async () => {
    const mockEval = createMockEvaluation(true);
    const mockModel = createMockModel(true);

    const results = await mockEval.evaluate({ model: mockModel });
    const expectedResults = {
      model_success: { true_count: 4, true_fraction: 0.8 },
      inclusionScorer: {
        true_count: 4,
        true_fraction: 0.8,
      },
      lengthScorer: {
        length: {
          mean: 14.4,
        },
      },
      model_latency: { mean: expect.any(Number) },
    };

    expect(results).toEqual(expectedResults);
  });
});
