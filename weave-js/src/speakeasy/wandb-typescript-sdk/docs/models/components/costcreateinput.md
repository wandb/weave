# CostCreateInput

## Example Usage

```typescript
import { CostCreateInput } from "wandb/models/components";

let value: CostCreateInput = {
  promptTokenCost: 6976.31,
  completionTokenCost: 602.25,
};
```

## Fields

| Field                                                                                                          | Type                                                                                                           | Required                                                                                                       | Description                                                                                                    |
| -------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `promptTokenCost`                                                                                              | *number*                                                                                                       | :heavy_check_mark:                                                                                             | N/A                                                                                                            |
| `completionTokenCost`                                                                                          | *number*                                                                                                       | :heavy_check_mark:                                                                                             | N/A                                                                                                            |
| `promptTokenCostUnit`                                                                                          | *string*                                                                                                       | :heavy_minus_sign:                                                                                             | The unit of the cost for the prompt tokens                                                                     |
| `completionTokenCostUnit`                                                                                      | *string*                                                                                                       | :heavy_minus_sign:                                                                                             | The unit of the cost for the completion tokens                                                                 |
| `effectiveDate`                                                                                                | [Date](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Date)                  | :heavy_minus_sign:                                                                                             | The date after which the cost is effective for, will default to the current date if not provided               |
| `providerId`                                                                                                   | *string*                                                                                                       | :heavy_minus_sign:                                                                                             | The provider of the LLM, e.g. 'openai' or 'mistral'. If not provided, the provider_id will be set to 'default' |