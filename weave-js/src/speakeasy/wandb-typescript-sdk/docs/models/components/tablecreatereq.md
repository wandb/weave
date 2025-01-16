# TableCreateReq

## Example Usage

```typescript
import { TableCreateReq } from "wandb/models/components";

let value: TableCreateReq = {
  table: {
    projectId: "<id>",
    rows: [
      {},
    ],
  },
};
```

## Fields

| Field                                                                              | Type                                                                               | Required                                                                           | Description                                                                        |
| ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `table`                                                                            | [components.TableSchemaForInsert](../../models/components/tableschemaforinsert.md) | :heavy_check_mark:                                                                 | N/A                                                                                |