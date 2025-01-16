# TableQueryReq

## Example Usage

```typescript
import { TableQueryReq } from "wandb/models/components";

let value: TableQueryReq = {
  projectId: "my_entity/my_project",
  digest: "aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims",
  filter: {
    rowDigests: [
      "aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims",
      "aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims",
    ],
  },
  limit: 100,
  offset: 10,
  sortBy: [
    {
      field: "col_a.prop_b",
      direction: "desc",
    },
  ],
};
```

## Fields

| Field                                                                                                                                                       | Type                                                                                                                                                        | Required                                                                                                                                                    | Description                                                                                                                                                 | Example                                                                                                                                                     |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `projectId`                                                                                                                                                 | *string*                                                                                                                                                    | :heavy_check_mark:                                                                                                                                          | The ID of the project                                                                                                                                       | my_entity/my_project                                                                                                                                        |
| `digest`                                                                                                                                                    | *string*                                                                                                                                                    | :heavy_check_mark:                                                                                                                                          | The digest of the table to query                                                                                                                            | aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims                                                                                             |
| `filter`                                                                                                                                                    | [components.TableRowFilter](../../models/components/tablerowfilter.md)                                                                                      | :heavy_minus_sign:                                                                                                                                          | Optional filter to apply to the query. See `TableRowFilter` for more details.                                                                               | {<br/>"row_digests": [<br/>"aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims",<br/>"aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims"<br/>]<br/>} |
| `limit`                                                                                                                                                     | *number*                                                                                                                                                    | :heavy_minus_sign:                                                                                                                                          | Maximum number of rows to return                                                                                                                            | 100                                                                                                                                                         |
| `offset`                                                                                                                                                    | *number*                                                                                                                                                    | :heavy_minus_sign:                                                                                                                                          | Number of rows to skip before starting to return rows                                                                                                       | 10                                                                                                                                                          |
| `sortBy`                                                                                                                                                    | [components.SortBy](../../models/components/sortby.md)[]                                                                                                    | :heavy_minus_sign:                                                                                                                                          | List of fields to sort by. Fields can be dot-separated to access dictionary values. No sorting uses the default table order (insertion order).              | [<br/>{<br/>"field": "col_a.prop_b",<br/>"order": "desc"<br/>}<br/>]                                                                                        |