# CostPurgeReq

## Example Usage

```typescript
import { CostPurgeReq } from "wandb/models/components";

let value: CostPurgeReq = {
  projectId: "entity/project",
  query: [
    "<value>",
  ],
};
```

## Fields

| Field                            | Type                             | Required                         | Description                      | Example                          |
| -------------------------------- | -------------------------------- | -------------------------------- | -------------------------------- | -------------------------------- |
| `projectId`                      | *string*                         | :heavy_check_mark:               | N/A                              | entity/project                   |
| `query`                          | *components.CostPurgeReqQuery*[] | :heavy_check_mark:               | N/A                              |                                  |