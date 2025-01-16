# ObjReadRes

## Example Usage

```typescript
import { ObjReadRes } from "wandb/models/components";

let value: ObjReadRes = {
  obj: {
    projectId: "<id>",
    objectId: "<id>",
    createdAt: new Date("2025-05-25T21:04:00.744Z"),
    digest: "<value>",
    versionIndex: 461479,
    isLatest: 780529,
    kind: "<value>",
    baseObjectClass: "<value>",
    val: "<value>",
  },
};
```

## Fields

| Field                                                        | Type                                                         | Required                                                     | Description                                                  |
| ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| `obj`                                                        | [components.ObjSchema](../../models/components/objschema.md) | :heavy_check_mark:                                           | N/A                                                          |