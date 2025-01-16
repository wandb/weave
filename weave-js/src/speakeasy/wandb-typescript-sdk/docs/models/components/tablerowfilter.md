# TableRowFilter

## Example Usage

```typescript
import { TableRowFilter } from "wandb/models/components";

let value: TableRowFilter = {
  rowDigests: [
    "aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims",
    "aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims",
  ],
};
```

## Fields

| Field                                                                                                                                    | Type                                                                                                                                     | Required                                                                                                                                 | Description                                                                                                                              | Example                                                                                                                                  |
| ---------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `rowDigests`                                                                                                                             | *string*[]                                                                                                                               | :heavy_minus_sign:                                                                                                                       | List of row digests to filter by                                                                                                         | [<br/>"aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims",<br/>"aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims"<br/>] |