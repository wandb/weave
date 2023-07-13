# StreamTable

A Weave StreamTable object enables continuous streaming of data from an application or service to W&B. This is an extension of the standard
wandb Table object to handle monitoring use cases. Instead of uploading a complete Table object once, you can
append data repeatedly to a StreamTable object with `.log([your data rows])`. 

## Create a StreamTable

```
from weave.monitoring import StreamTable
st = StreamTable("my_entity_name/my_project_name/my_table_name")
```

## Log data to a StreamTable

## Usage notes 

