# FeedbackCreateReq

## Example Usage

```typescript
import { FeedbackCreateReq } from "wandb/models/components";

let value: FeedbackCreateReq = {
  projectId: "entity/project",
  weaveRef: "weave:///entity/project/object/name:digest",
  creator: "Jane Smith",
  feedbackType: "custom",
  payload: {},
};
```

## Fields

| Field                                                               | Type                                                                | Required                                                            | Description                                                         | Example                                                             |
| ------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `projectId`                                                         | *string*                                                            | :heavy_check_mark:                                                  | N/A                                                                 | entity/project                                                      |
| `weaveRef`                                                          | *string*                                                            | :heavy_check_mark:                                                  | N/A                                                                 | weave:///entity/project/object/name:digest                          |
| `creator`                                                           | *string*                                                            | :heavy_minus_sign:                                                  | N/A                                                                 | Jane Smith                                                          |
| `feedbackType`                                                      | *string*                                                            | :heavy_check_mark:                                                  | N/A                                                                 | custom                                                              |
| `payload`                                                           | [components.Payload](../../models/components/payload.md)            | :heavy_check_mark:                                                  | N/A                                                                 | {<br/>"key": "value"<br/>}                                          |
| `wbUserId`                                                          | *string*                                                            | :heavy_minus_sign:                                                  | Do not set directly. Server will automatically populate this field. |                                                                     |