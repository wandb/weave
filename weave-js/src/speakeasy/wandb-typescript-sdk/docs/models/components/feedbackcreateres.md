# FeedbackCreateRes

## Example Usage

```typescript
import { FeedbackCreateRes } from "wandb/models/components";

let value: FeedbackCreateRes = {
  id: "<id>",
  createdAt: new Date("2023-05-22T07:16:38.400Z"),
  wbUserId: "<id>",
  payload: {},
};
```

## Fields

| Field                                                                                         | Type                                                                                          | Required                                                                                      | Description                                                                                   |
| --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `id`                                                                                          | *string*                                                                                      | :heavy_check_mark:                                                                            | N/A                                                                                           |
| `createdAt`                                                                                   | [Date](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Date) | :heavy_check_mark:                                                                            | N/A                                                                                           |
| `wbUserId`                                                                                    | *string*                                                                                      | :heavy_check_mark:                                                                            | N/A                                                                                           |
| `payload`                                                                                     | [components.FeedbackCreateResPayload](../../models/components/feedbackcreaterespayload.md)    | :heavy_check_mark:                                                                            | N/A                                                                                           |