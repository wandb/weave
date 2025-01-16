# FeedbackPurgeReq

## Example Usage

```typescript
import { FeedbackPurgeReq } from "wandb/models/components";

let value: FeedbackPurgeReq = {
  projectId: "entity/project",
  query: [
    4386.01,
  ],
};
```

## Fields

| Field                                | Type                                 | Required                             | Description                          | Example                              |
| ------------------------------------ | ------------------------------------ | ------------------------------------ | ------------------------------------ | ------------------------------------ |
| `projectId`                          | *string*                             | :heavy_check_mark:                   | N/A                                  | entity/project                       |
| `query`                              | *components.FeedbackPurgeReqQuery*[] | :heavy_check_mark:                   | N/A                                  |                                      |