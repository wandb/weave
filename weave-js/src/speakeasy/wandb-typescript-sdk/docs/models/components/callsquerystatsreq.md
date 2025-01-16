# CallsQueryStatsReq

## Example Usage

```typescript
import { CallsQueryStatsReq } from "wandb/models/components";

let value: CallsQueryStatsReq = {
  projectId: "<id>",
};
```

## Fields

| Field                                                            | Type                                                             | Required                                                         | Description                                                      |
| ---------------------------------------------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------------- |
| `projectId`                                                      | *string*                                                         | :heavy_check_mark:                                               | N/A                                                              |
| `filter`                                                         | [components.CallsFilter](../../models/components/callsfilter.md) | :heavy_minus_sign:                                               | N/A                                                              |
| `query`                                                          | *components.Query*[]                                             | :heavy_minus_sign:                                               | N/A                                                              |