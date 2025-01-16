# ObjQueryRes

## Example Usage

```typescript
import { ObjQueryRes } from "wandb/models/components";

let value: ObjQueryRes = {
  objs: [
    {
      projectId: "<id>",
      objectId: "<id>",
      createdAt: new Date("2025-11-01T08:34:16.299Z"),
      digest: "<value>",
      versionIndex: 521848,
      isLatest: 414662,
      kind: "<value>",
      baseObjectClass: "<value>",
      val: "<value>",
    },
  ],
};
```

## Fields

| Field                                                          | Type                                                           | Required                                                       | Description                                                    |
| -------------------------------------------------------------- | -------------------------------------------------------------- | -------------------------------------------------------------- | -------------------------------------------------------------- |
| `objs`                                                         | [components.ObjSchema](../../models/components/objschema.md)[] | :heavy_check_mark:                                             | N/A                                                            |