# CallsDeleteReq

## Example Usage

```typescript
import { CallsDeleteReq } from "wandb/models/components";

let value: CallsDeleteReq = {
  projectId: "<id>",
  callIds: [
    "<value>",
  ],
};
```

## Fields

| Field                                                               | Type                                                                | Required                                                            | Description                                                         |
| ------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `projectId`                                                         | *string*                                                            | :heavy_check_mark:                                                  | N/A                                                                 |
| `callIds`                                                           | *string*[]                                                          | :heavy_check_mark:                                                  | N/A                                                                 |
| `wbUserId`                                                          | *string*                                                            | :heavy_minus_sign:                                                  | Do not set directly. Server will automatically populate this field. |