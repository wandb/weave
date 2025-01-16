# ObjQueryReq

## Example Usage

```typescript
import { ObjQueryReq } from "wandb/models/components";

let value: ObjQueryReq = {
  projectId: "user/project",
  filter: {
    objectIds: [
      "my_favorite_model",
    ],
    latestOnly: true,
  },
  limit: 100,
  offset: 0,
  sortBy: [
    {
      field: "created_at",
      direction: "desc",
    },
  ],
};
```

## Fields

| Field                                                                                               | Type                                                                                                | Required                                                                                            | Description                                                                                         | Example                                                                                             |
| --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `projectId`                                                                                         | *string*                                                                                            | :heavy_check_mark:                                                                                  | The ID of the project to query                                                                      | user/project                                                                                        |
| `filter`                                                                                            | [components.ObjectVersionFilter](../../models/components/objectversionfilter.md)                    | :heavy_minus_sign:                                                                                  | Filter criteria for the query. See `ObjectVersionFilter`                                            | {<br/>"latest_only": true,<br/>"object_ids": [<br/>"my_favorite_model"<br/>]<br/>}                  |
| `limit`                                                                                             | *number*                                                                                            | :heavy_minus_sign:                                                                                  | Maximum number of results to return                                                                 | 100                                                                                                 |
| `offset`                                                                                            | *number*                                                                                            | :heavy_minus_sign:                                                                                  | Number of results to skip before returning                                                          | 0                                                                                                   |
| `sortBy`                                                                                            | [components.SortBy](../../models/components/sortby.md)[]                                            | :heavy_minus_sign:                                                                                  | Sorting criteria for the query results. Currently only supports 'object_id' and 'created_at'.       | [<br/>{<br/>"direction": "desc",<br/>"field": "created_at"<br/>}<br/>]                              |
| `metadataOnly`                                                                                      | *boolean*                                                                                           | :heavy_minus_sign:                                                                                  | If true, the `val` column is not read from the database and is empty.All other fields are returned. |                                                                                                     |