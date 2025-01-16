# EndedCallSchemaForInsert

## Example Usage

```typescript
import { EndedCallSchemaForInsert } from "wandb/models/components";

let value: EndedCallSchemaForInsert = {
  projectId: "<id>",
  id: "<id>",
  endedAt: new Date("2024-04-24T14:17:38.418Z"),
  summary: {},
};
```

## Fields

| Field                                                                                         | Type                                                                                          | Required                                                                                      | Description                                                                                   |
| --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `projectId`                                                                                   | *string*                                                                                      | :heavy_check_mark:                                                                            | N/A                                                                                           |
| `id`                                                                                          | *string*                                                                                      | :heavy_check_mark:                                                                            | N/A                                                                                           |
| `endedAt`                                                                                     | [Date](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Date) | :heavy_check_mark:                                                                            | N/A                                                                                           |
| `exception`                                                                                   | *string*                                                                                      | :heavy_minus_sign:                                                                            | N/A                                                                                           |
| `output`                                                                                      | *any*                                                                                         | :heavy_minus_sign:                                                                            | N/A                                                                                           |
| `summary`                                                                                     | [components.SummaryInsertMap](../../models/components/summaryinsertmap.md)                    | :heavy_check_mark:                                                                            | N/A                                                                                           |