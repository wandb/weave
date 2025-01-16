# TableQueryRes

## Example Usage

```typescript
import { TableQueryRes } from "wandb/models/components";

let value: TableQueryRes = {
  rows: [
    {
      digest: "<value>",
      val: "<value>",
    },
  ],
};
```

## Fields

| Field                                                                    | Type                                                                     | Required                                                                 | Description                                                              |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------------ | ------------------------------------------------------------------------ | ------------------------------------------------------------------------ |
| `rows`                                                                   | [components.TableRowSchema](../../models/components/tablerowschema.md)[] | :heavy_check_mark:                                                       | N/A                                                                      |