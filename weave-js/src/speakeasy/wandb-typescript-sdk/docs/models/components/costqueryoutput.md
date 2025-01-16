# CostQueryOutput

## Example Usage

```typescript
import { CostQueryOutput } from "wandb/models/components";

let value: CostQueryOutput = {
  id: "2341-asdf-asdf",
  llmId: "gpt4",
  promptTokenCost: 1,
  completionTokenCost: 1,
  promptTokenCostUnit: "USD",
  completionTokenCostUnit: "USD",
  effectiveDate: new Date("2024-01-01T00:00:00Z"),
  providerId: "openai",
};
```

## Fields

| Field                                                                                         | Type                                                                                          | Required                                                                                      | Description                                                                                   | Example                                                                                       |
| --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `id`                                                                                          | *string*                                                                                      | :heavy_minus_sign:                                                                            | N/A                                                                                           | 2341-asdf-asdf                                                                                |
| `llmId`                                                                                       | *string*                                                                                      | :heavy_minus_sign:                                                                            | N/A                                                                                           | gpt4                                                                                          |
| `promptTokenCost`                                                                             | *number*                                                                                      | :heavy_minus_sign:                                                                            | N/A                                                                                           | 1                                                                                             |
| `completionTokenCost`                                                                         | *number*                                                                                      | :heavy_minus_sign:                                                                            | N/A                                                                                           | 1                                                                                             |
| `promptTokenCostUnit`                                                                         | *string*                                                                                      | :heavy_minus_sign:                                                                            | N/A                                                                                           | USD                                                                                           |
| `completionTokenCostUnit`                                                                     | *string*                                                                                      | :heavy_minus_sign:                                                                            | N/A                                                                                           | USD                                                                                           |
| `effectiveDate`                                                                               | [Date](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Date) | :heavy_minus_sign:                                                                            | N/A                                                                                           | 2024-01-01 00:00:00 +0000 UTC                                                                 |
| `providerId`                                                                                  | *string*                                                                                      | :heavy_minus_sign:                                                                            | N/A                                                                                           | openai                                                                                        |