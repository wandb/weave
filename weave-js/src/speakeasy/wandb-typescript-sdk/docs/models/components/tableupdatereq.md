# TableUpdateReq

## Example Usage

```typescript
import { TableUpdateReq } from "wandb/models/components";

let value: TableUpdateReq = {
  projectId: "<id>",
  baseDigest: "<value>",
  updates: [
    {
      pop: {
        index: 568434,
      },
    },
  ],
};
```

## Fields

| Field                  | Type                   | Required               | Description            |
| ---------------------- | ---------------------- | ---------------------- | ---------------------- |
| `projectId`            | *string*               | :heavy_check_mark:     | N/A                    |
| `baseDigest`           | *string*               | :heavy_check_mark:     | N/A                    |
| `updates`              | *components.Updates*[] | :heavy_check_mark:     | N/A                    |