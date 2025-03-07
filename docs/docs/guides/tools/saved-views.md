# Saved Views

In Weave, _saved views_ allow you to customize how you interact with traced function calls and evaluations. By defining a saved view, you can configure filters, sorting, and column visibility to quickly access relevant data.

You can create, modify, and save views directly in the Weave Python SDK or through the UI. The Python SDK provides fine-grained control for programmatic filtering and querying, while the UI makes it easy to explore and save different table configurations in the **Traces** and **Evals** tabs.

This guide covers:

- [How to create and modify Saved Views in the Python SDK](#saved-views-in-the-python-sdk).
- [How to create and interact with Saved Views in the Weave UI](#saved-views-in-the-ui).

## Saved views in the Python SDK

The `SavedView` class in Weave provides a way to save, filter, sort, and customize views of trace and evals data. 

### Initialize a `SavedView`

Initialize a `SavedView` instance in your Weave project:

```python
import weave
client = weave.init(<my_project>)

view = weave.SavedView()
```

### Visualize the `SavedView` as a grid

Use `.to_grid()` to represent the saved view as a grdi. Specify the maximum number of rows to display with `limit`.

```python
view.to_grid(limit=5)
```

Display the grid representation using `.show()`:

```python
to_grid().show()
```

### Set displayed columns

Use `.set_columns()` to set the columns to be displayed in the view. Specify one or more columns to be displayed.

```python
view.set_columns("id", "op_name")
```

### Add columns

Use `.add_column()` to add one or more new columns to the view. Specify one or more columns to be added.

```python
view.add_column("started_at", "Created")
```

### Sort columns

Use `.sort_by()` to sort results based on a specific column. Specify the column name to be sorted and the sort order (`asc` or `desc`).

```python
view.sort_by("started_at", "desc")
```

### Filter by operation name

In Weave, every trace or eval is associated with an operation name.
Use `.filter_op()` to filter the `SavedView` to only include calls where that specific operation was executed. 

```python
view.filter_op("Evaluation.predict_and_score")
```

:::tip
`.filter_op()` is a shortcut for filtering by operation name. It ensures the correct URI format is used automatically. Alternatively, you can achieve the same result with `.add_filter("op_name", "equals", <operation_name>)`.
:::

### Filter by operator and condition

Use `.add_filter()` to apply a custom filter to the view. Define the filter using one of the [supported filter operators](#filter-operators) and a condition.

```python
view.add_filter("output.model_latency", ">=", 5)
```

#### Filter operators

| Operator | Description | Example |
|----------|-------------|---------|
| `"contains"` | Checks if a string contains a substring. | `view.add_filter("output.status", "contains", "error")` |
| `"equals"` | Checks if a string is exactly equal to a given value. | `view.add_filter("user.name", "equals", "Alice")` |
| `"in"` | Checks if a string is in a list of values. | `view.add_filter("category", "in", ["A", "B", "C"])` |
| `"="` | Checks if a number is equal to a value. | `view.add_filter("output.score", "=", 80)` |
| `"≠", "!="` | Checks if a number is not equal to a value. | `view.add_filter("metrics.loss", "!=", 0.5)` |
| `"<"` | Checks if a number is less than a value. | `view.add_filter("age", "<", 30)` |
| `"≤", "<="` | Checks if a number is less than or equal to a value. | `view.add_filter("metric.value", "<=", 100)` |
| `">"` | Checks if a number is greater than a value. | `view.add_filter("output.score", ">", 90)` |
| `"≥", ">="` | Checks if a number is greater than or equal to a value. | `view.add_filter("output.model_latency", ">=", 5)` |
| `"is"` | Checks if a boolean field is `True` or `False`. | `view.add_filter("is_active", "is", True)` |
| `"after"` | Checks if a date is after a given timestamp. | `view.add_filter("started_at", "after", "2024-01-01")` |
| `"before"` | Checks if a date is before a given timestamp. | `view.add_filter("ended_at", "before", "2024-12-31")` |
| `"is empty"` | Checks if a field is empty (`None` or `""`). | `view.add_filter("comments", "is empty", None)` |
| `"is not empty"` | Checks if a field is not empty. | `view.add_filter("attachments", "is not empty", None)` |

### Remove filters

Use `.remove_filter()` to remove a specific filter from the view by index or field name.

```python
view.remove_filter("output.model_latency")
```

Use `.remove_filters()` to remove all filters.

```python
view.remove_filters()
```

### Save the `SavedView`

Use `.save()` to publish the saved view to Weave.

```python
view.save()
```

### Retrieve function calls

Use `.get_calls()` to retrieve function calls that match the filters in the saved view. You can specify optional parameters such as `limit` and `offset`.

```python
calls = view.get_calls(limit=10)
```

## Saved views in the UI 

You can create, load, rename, and edit saved views in the Weave UI. For fine-grained control, use the [Python SDK](#saved-views-in-the-python-sdk).

### Create a saved view

1. Navigate to your **Traces** or **Evals** tab.
2. Adjust any of the following variables in your table configuration:
   - Filters
   - Sort order
   - Page size
   - Column visibility
   - Column pinning
3. Save the view using one of two options:
   - In the upper right hand corner, click **Save view**. 
   - Click the hamburger menu to the left of **Save view**. In the dropdown menu, click **+ Save as new view**.

### Load a saved view

1. Navigate to your **Traces** or **Evals** tab.
2. Click the hamburger menu to the left of the tab title. A dropdown menu showing all saved views displays. 
3. Click the view that you want to access. The saved view displays in the **Traces** or **Evals** tab. 

### Rename a saved view

1. Follow the steps described in [Access a saved view](#access-a-saved-view).
2. In the upper lefthand corner of the **Traces** or **Evals** tab, click the view name.
3. Enter a new name for the view.
4. To save the new view name, press **Enter**.

### Edit a saved view

1. Follow the steps described in [Access a saved view](#access-a-saved-view).
2. Adjust your table configuration.
3. In the upper right hand corner, click **Save view**. 

### Delete a saved view 

:::important
You can delete a view if you believe it is no longer useful to you and your team. This cannot be undone.
:::

1. Navigate to your **Traces** or **Evals** tab.
2. [Load the view](#load-a-saved-view) that you want to delete.
3. Click the hamburger menu to the left of **Save view**. 
4. In the dropdown menu, click **Delete view**.
5. In the pop-up modal, confirm by clicking **Delete view**. Alternatively, click **Cancel** to stop deletion.

### Return to the default view

1. Navigate to your **Traces** or **Evals** tab.
2. Click the hamburger menu to the right of the **Traces** or **Evals** tab. A dropdown menu showing all saved views displays. 
3. At the bottom on the menu, click **Traces** or **Evals**. The default view displays.
