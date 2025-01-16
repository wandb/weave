# TableSchemaForInsert

## Example Usage

```typescript
import { TableSchemaForInsert } from "wandb/models/components";

let value: TableSchemaForInsert = {
  projectId: "<id>",
  rows: [
    {},
  ],
};
```

## Fields

| Field                                                | Type                                                 | Required                                             | Description                                          |
| ---------------------------------------------------- | ---------------------------------------------------- | ---------------------------------------------------- | ---------------------------------------------------- |
| `projectId`                                          | *string*                                             | :heavy_check_mark:                                   | N/A                                                  |
| `rows`                                               | [components.Rows](../../models/components/rows.md)[] | :heavy_check_mark:                                   | N/A                                                  |