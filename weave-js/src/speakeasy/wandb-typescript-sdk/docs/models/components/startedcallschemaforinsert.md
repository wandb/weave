# StartedCallSchemaForInsert

## Example Usage

```typescript
import { StartedCallSchemaForInsert } from "wandb/models/components";

let value: StartedCallSchemaForInsert = {
  projectId: "<id>",
  opName: "<value>",
  startedAt: new Date("2024-04-09T07:48:57.030Z"),
  attributes: {},
  inputs: {},
};
```

## Fields

| Field                                                                                         | Type                                                                                          | Required                                                                                      | Description                                                                                   |
| --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `projectId`                                                                                   | *string*                                                                                      | :heavy_check_mark:                                                                            | N/A                                                                                           |
| `id`                                                                                          | *string*                                                                                      | :heavy_minus_sign:                                                                            | N/A                                                                                           |
| `opName`                                                                                      | *string*                                                                                      | :heavy_check_mark:                                                                            | N/A                                                                                           |
| `displayName`                                                                                 | *string*                                                                                      | :heavy_minus_sign:                                                                            | N/A                                                                                           |
| `traceId`                                                                                     | *string*                                                                                      | :heavy_minus_sign:                                                                            | N/A                                                                                           |
| `parentId`                                                                                    | *string*                                                                                      | :heavy_minus_sign:                                                                            | N/A                                                                                           |
| `startedAt`                                                                                   | [Date](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Date) | :heavy_check_mark:                                                                            | N/A                                                                                           |
| `attributes`                                                                                  | [components.Attributes](../../models/components/attributes.md)                                | :heavy_check_mark:                                                                            | N/A                                                                                           |
| `inputs`                                                                                      | [components.Inputs](../../models/components/inputs.md)                                        | :heavy_check_mark:                                                                            | N/A                                                                                           |
| `wbUserId`                                                                                    | *string*                                                                                      | :heavy_minus_sign:                                                                            | Do not set directly. Server will automatically populate this field.                           |
| `wbRunId`                                                                                     | *string*                                                                                      | :heavy_minus_sign:                                                                            | N/A                                                                                           |