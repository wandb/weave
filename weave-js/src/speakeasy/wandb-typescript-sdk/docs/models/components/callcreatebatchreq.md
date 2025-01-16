# CallCreateBatchReq

## Example Usage

```typescript
import { CallCreateBatchReq } from "wandb/models/components";

let value: CallCreateBatchReq = {
  batch: [
    {
      req: {
        end: {
          projectId: "<id>",
          id: "<id>",
          endedAt: new Date("2024-08-02T16:03:07.089Z"),
          summary: {},
        },
      },
    },
  ],
};
```

## Fields

| Field                | Type                 | Required             | Description          |
| -------------------- | -------------------- | -------------------- | -------------------- |
| `batch`              | *components.Batch*[] | :heavy_check_mark:   | N/A                  |