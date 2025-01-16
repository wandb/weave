# TableQueryStatsReq

## Example Usage

```typescript
import { TableQueryStatsReq } from "wandb/models/components";

let value: TableQueryStatsReq = {
  projectId: "my_entity/my_project",
  digest: "aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims",
};
```

## Fields

| Field                                                           | Type                                                            | Required                                                        | Description                                                     | Example                                                         |
| --------------------------------------------------------------- | --------------------------------------------------------------- | --------------------------------------------------------------- | --------------------------------------------------------------- | --------------------------------------------------------------- |
| `projectId`                                                     | *string*                                                        | :heavy_check_mark:                                              | The ID of the project                                           | my_entity/my_project                                            |
| `digest`                                                        | *string*                                                        | :heavy_check_mark:                                              | The digest of the table to query                                | aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims |