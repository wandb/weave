# CallEndReq

## Example Usage

```typescript
import { CallEndReq } from "wandb/models/components";

let value: CallEndReq = {
  end: {
    projectId: "<id>",
    id: "<id>",
    endedAt: new Date("2024-12-08T21:35:55.501Z"),
    summary: {},
  },
};
```

## Fields

| Field                                                                                      | Type                                                                                       | Required                                                                                   | Description                                                                                |
| ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| `end`                                                                                      | [components.EndedCallSchemaForInsert](../../models/components/endedcallschemaforinsert.md) | :heavy_check_mark:                                                                         | N/A                                                                                        |