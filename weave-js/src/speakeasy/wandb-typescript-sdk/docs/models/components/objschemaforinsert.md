# ObjSchemaForInsert

## Example Usage

```typescript
import { ObjSchemaForInsert } from "wandb/models/components";

let value: ObjSchemaForInsert = {
  projectId: "<id>",
  objectId: "<id>",
  val: "<value>",
};
```

## Fields

| Field                | Type                 | Required             | Description          |
| -------------------- | -------------------- | -------------------- | -------------------- |
| `projectId`          | *string*             | :heavy_check_mark:   | N/A                  |
| `objectId`           | *string*             | :heavy_check_mark:   | N/A                  |
| `val`                | *any*                | :heavy_check_mark:   | N/A                  |
| `setBaseObjectClass` | *string*             | :heavy_minus_sign:   | N/A                  |