# CallBatchEndMode

## Example Usage

```typescript
import { CallBatchEndMode } from "wandb/models/components";

let value: CallBatchEndMode = {
  req: {
    end: {
      projectId: "<id>",
      id: "<id>",
      endedAt: new Date("2025-10-11T10:53:38.306Z"),
      summary: {},
    },
  },
};
```

## Fields

| Field                                                          | Type                                                           | Required                                                       | Description                                                    |
| -------------------------------------------------------------- | -------------------------------------------------------------- | -------------------------------------------------------------- | -------------------------------------------------------------- |
| `mode`                                                         | *string*                                                       | :heavy_minus_sign:                                             | N/A                                                            |
| `req`                                                          | [components.CallEndReq](../../models/components/callendreq.md) | :heavy_check_mark:                                             | N/A                                                            |