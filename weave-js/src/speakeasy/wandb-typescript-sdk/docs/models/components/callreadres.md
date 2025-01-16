# CallReadRes

## Example Usage

```typescript
import { CallReadRes } from "wandb/models/components";

let value: CallReadRes = {
  call: {
    id: "<id>",
    projectId: "<id>",
    opName: "<value>",
    traceId: "<id>",
    startedAt: new Date("2023-03-19T20:31:56.909Z"),
    attributes: {},
    inputs: {},
  },
};
```

## Fields

| Field                                                          | Type                                                           | Required                                                       | Description                                                    |
| -------------------------------------------------------------- | -------------------------------------------------------------- | -------------------------------------------------------------- | -------------------------------------------------------------- |
| `call`                                                         | [components.CallSchema](../../models/components/callschema.md) | :heavy_check_mark:                                             | N/A                                                            |