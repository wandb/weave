# SummaryInsertMap

## Example Usage

```typescript
import { SummaryInsertMap } from "wandb/models/components";

let value: SummaryInsertMap = {};
```

## Fields

| Field                                                                                  | Type                                                                                   | Required                                                                               | Description                                                                            |
| -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `usage`                                                                                | Record<string, [components.LLMUsageSchema](../../models/components/llmusageschema.md)> | :heavy_minus_sign:                                                                     | N/A                                                                                    |
| `additionalProperties`                                                                 | Record<string, *any*>                                                                  | :heavy_minus_sign:                                                                     | N/A                                                                                    |