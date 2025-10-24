import { Evaluation } from "../evaluation";
import { Dataset } from "../dataset";
// import { Op } from "../opType";
import { op } from "../op";

describe("Evaluation", () => {
  test("summarizeResults with failed predictions and scorers", async () => {
    // Mock dataset
    const mockDataset = new Dataset({
      rows: [
        { id: 0, text: "Example 0" },
        { id: 1, text: "Example 1" },
        { id: 2, text: "Example 2" },
        { id: 3, text: "Example 3" },
        { id: 4, text: "Example 4" },
      ],
    });

    // Mock model
    const mockModel = op(async function mockPrediction({
      datasetRow,
    }: {
      datasetRow: {
        id: number;
        text: string;
      };
    }) {
      if (datasetRow.id === 0) throw new Error("Model failed");
      return `Prediction for ${datasetRow.text}`;
    });

    // Mock scorers
    const mockScorers = [
      op(async function lengthScorer({
        datasetRow,
        modelOutput,
      }: {
        datasetRow: { id: number; text: string };
        modelOutput: string;
      }) {
        if (datasetRow.id === 3) throw new Error("Scorer 1 failed");
        return {
          explanation: "length is " + modelOutput.length,
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

    // Create Evaluation instance
    const evaluation = new Evaluation({
      dataset: mockDataset,
      scorers: mockScorers,
    });

    // Run evaluation
    const results = await evaluation.evaluate({ model: mockModel });

    // Expected summarized results
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

    // Check results
    expect(results).toEqual(expectedResults);
  });
});
