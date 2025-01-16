# CallUpdateReq

## Example Usage

```typescript
import { CallUpdateReq } from "wandb/models/components";

let value: CallUpdateReq = {
  projectId: "<id>",
  callId: "<id>",
};
```

## Fields

| Field                                                               | Type                                                                | Required                                                            | Description                                                         |
| ------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `projectId`                                                         | *string*                                                            | :heavy_check_mark:                                                  | N/A                                                                 |
| `callId`                                                            | *string*                                                            | :heavy_check_mark:                                                  | N/A                                                                 |
| `displayName`                                                       | *string*                                                            | :heavy_minus_sign:                                                  | N/A                                                                 |
| `wbUserId`                                                          | *string*                                                            | :heavy_minus_sign:                                                  | Do not set directly. Server will automatically populate this field. |