# ObjCreateReq

## Example Usage

```typescript
import { ObjCreateReq } from "wandb/models/components";

let value: ObjCreateReq = {
  obj: {
    projectId: "<id>",
    objectId: "<id>",
    val: "<value>",
  },
};
```

## Fields

| Field                                                                          | Type                                                                           | Required                                                                       | Description                                                                    |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------ |
| `obj`                                                                          | [components.ObjSchemaForInsert](../../models/components/objschemaforinsert.md) | :heavy_check_mark:                                                             | N/A                                                                            |