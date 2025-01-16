# TableCreateRes

## Example Usage

```typescript
import { TableCreateRes } from "wandb/models/components";

let value: TableCreateRes = {
  digest: "<value>",
};
```

## Fields

| Field                                     | Type                                      | Required                                  | Description                               |
| ----------------------------------------- | ----------------------------------------- | ----------------------------------------- | ----------------------------------------- |
| `digest`                                  | *string*                                  | :heavy_check_mark:                        | N/A                                       |
| `rowDigests`                              | *string*[]                                | :heavy_minus_sign:                        | The digests of the rows that were created |