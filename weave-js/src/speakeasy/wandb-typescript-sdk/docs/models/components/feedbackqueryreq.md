# FeedbackQueryReq

## Example Usage

```typescript
import { FeedbackQueryReq } from "wandb/models/components";

let value: FeedbackQueryReq = {
  projectId: "entity/project",
  fields: [
    "id",
    "feedback_type",
    "payload.note",
  ],
  limit: 10,
  offset: 0,
};
```

## Fields

| Field                                                    | Type                                                     | Required                                                 | Description                                              | Example                                                  |
| -------------------------------------------------------- | -------------------------------------------------------- | -------------------------------------------------------- | -------------------------------------------------------- | -------------------------------------------------------- |
| `projectId`                                              | *string*                                                 | :heavy_check_mark:                                       | N/A                                                      | entity/project                                           |
| `fields`                                                 | *string*[]                                               | :heavy_minus_sign:                                       | N/A                                                      | [<br/>"id",<br/>"feedback_type",<br/>"payload.note"<br/>] |
| `query`                                                  | *components.FeedbackQueryReqQuery*[]                     | :heavy_minus_sign:                                       | N/A                                                      |                                                          |
| `sortBy`                                                 | [components.SortBy](../../models/components/sortby.md)[] | :heavy_minus_sign:                                       | N/A                                                      |                                                          |
| `limit`                                                  | *number*                                                 | :heavy_minus_sign:                                       | N/A                                                      | 10                                                       |
| `offset`                                                 | *number*                                                 | :heavy_minus_sign:                                       | N/A                                                      | 0                                                        |