# CostCreateReq

## Example Usage

```typescript
import { CostCreateReq } from "wandb/models/components";

let value: CostCreateReq = {
  projectId: "entity/project",
  costs: {
    "key": {
      promptTokenCost: 3595.08,
      completionTokenCost: 4370.32,
    },
  },
};
```

## Fields

| Field                                                                                    | Type                                                                                     | Required                                                                                 | Description                                                                              | Example                                                                                  |
| ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `projectId`                                                                              | *string*                                                                                 | :heavy_check_mark:                                                                       | N/A                                                                                      | entity/project                                                                           |
| `costs`                                                                                  | Record<string, [components.CostCreateInput](../../models/components/costcreateinput.md)> | :heavy_check_mark:                                                                       | N/A                                                                                      |                                                                                          |
| `wbUserId`                                                                               | *string*                                                                                 | :heavy_minus_sign:                                                                       | Do not set directly. Server will automatically populate this field.                      |                                                                                          |