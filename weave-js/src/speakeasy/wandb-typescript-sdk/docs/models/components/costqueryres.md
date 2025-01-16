# CostQueryRes

## Example Usage

```typescript
import { CostQueryRes } from "wandb/models/components";

let value: CostQueryRes = {
  results: [
    {
      id: "2341-asdf-asdf",
      llmId: "gpt4",
      promptTokenCost: 1,
      completionTokenCost: 1,
      promptTokenCostUnit: "USD",
      completionTokenCostUnit: "USD",
      effectiveDate: new Date("2024-01-01T00:00:00Z"),
      providerId: "openai",
    },
  ],
};
```

## Fields

| Field                                                                      | Type                                                                       | Required                                                                   | Description                                                                |
| -------------------------------------------------------------------------- | -------------------------------------------------------------------------- | -------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `results`                                                                  | [components.CostQueryOutput](../../models/components/costqueryoutput.md)[] | :heavy_check_mark:                                                         | N/A                                                                        |