# CallStartReq

## Example Usage

```typescript
import { CallStartReq } from "wandb/models/components";

let value: CallStartReq = {
  start: {
    projectId: "<id>",
    opName: "<value>",
    startedAt: new Date("2024-08-20T04:36:26.084Z"),
    attributes: {},
    inputs: {},
  },
};
```

## Fields

| Field                                                                                          | Type                                                                                           | Required                                                                                       | Description                                                                                    |
| ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `start`                                                                                        | [components.StartedCallSchemaForInsert](../../models/components/startedcallschemaforinsert.md) | :heavy_check_mark:                                                                             | N/A                                                                                            |