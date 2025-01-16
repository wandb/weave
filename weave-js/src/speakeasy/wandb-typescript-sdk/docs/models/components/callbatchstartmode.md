# CallBatchStartMode

## Example Usage

```typescript
import { CallBatchStartMode } from "wandb/models/components";

let value: CallBatchStartMode = {
  req: {
    start: {
      projectId: "<id>",
      opName: "<value>",
      startedAt: new Date("2024-09-14T13:50:38.886Z"),
      attributes: {},
      inputs: {},
    },
  },
};
```

## Fields

| Field                                                              | Type                                                               | Required                                                           | Description                                                        |
| ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `mode`                                                             | *string*                                                           | :heavy_minus_sign:                                                 | N/A                                                                |
| `req`                                                              | [components.CallStartReq](../../models/components/callstartreq.md) | :heavy_check_mark:                                                 | N/A                                                                |