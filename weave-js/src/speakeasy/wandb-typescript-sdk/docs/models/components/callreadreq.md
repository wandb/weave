# CallReadReq

## Example Usage

```typescript
import { CallReadReq } from "wandb/models/components";

let value: CallReadReq = {
  projectId: "<id>",
  id: "<id>",
};
```

## Fields

| Field              | Type               | Required           | Description        |
| ------------------ | ------------------ | ------------------ | ------------------ |
| `projectId`        | *string*           | :heavy_check_mark: | N/A                |
| `id`               | *string*           | :heavy_check_mark: | N/A                |
| `includeCosts`     | *boolean*          | :heavy_minus_sign: | N/A                |