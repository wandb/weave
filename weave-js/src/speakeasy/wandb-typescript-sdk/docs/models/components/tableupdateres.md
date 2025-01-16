# TableUpdateRes

## Example Usage

```typescript
import { TableUpdateRes } from "wandb/models/components";

let value: TableUpdateRes = {
  digest: "<value>",
};
```

## Fields

| Field                                     | Type                                      | Required                                  | Description                               |
| ----------------------------------------- | ----------------------------------------- | ----------------------------------------- | ----------------------------------------- |
| `digest`                                  | *string*                                  | :heavy_check_mark:                        | N/A                                       |
| `updatedRowDigests`                       | *string*[]                                | :heavy_minus_sign:                        | The digests of the rows that were updated |