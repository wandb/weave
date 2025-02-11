import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Datasets

Weave `Dataset`s help you to organize, collect, track, and version examples for LLM application evaluation for easy comparison. You can create and interact with `Dataset`s programmatically and via the UI. 

This page describes:

- Basic `Dataset` operations in Python and TypeScript and how to get started  
- How to create a `Dataset` in Python and TypeScript from objects such as Weave [calls](../tracking/tracing.mdx)
- Available operations on a `Dataset` in the UI

## `Dataset` quickstart

The following code samples demonstrate how to perform fundamental `Dataset` operations using Python and TypeScript. Using the SDKs, you can:

- Create a `Dataset`
- Publish the `Dataset`
- Retrieve the `Dataset`
- Access a specific example in the `Dataset`

Select a tab to see Python and TypeScript-specific code. 

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    ```python
    import weave
    from weave import Dataset
    # Initialize Weave
    weave.init('intro-example')

    # Create a dataset
    dataset = Dataset(
        name='grammar',
        rows=[
            {'id': '0', 'sentence': "He no likes ice cream.", 'correction': "He doesn't like ice cream."},
            {'id': '1', 'sentence': "She goed to the store.", 'correction': "She went to the store."},
            {'id': '2', 'sentence': "They plays video games all day.", 'correction': "They play video games all day."}
        ]
    )

    # Publish the dataset
    weave.publish(dataset)

    # Retrieve the dataset
    dataset_ref = weave.ref('grammar').get()

    # Access a specific example
    example_label = dataset_ref.rows[2]['sentence']
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```typescript
    import * as weave from 'weave';

    // Initialize Weave
    await weave.init('intro-example');

    // Create a dataset
    const dataset = new weave.Dataset({
        name: 'grammar',
        rows: [
            {id: '0', sentence: "He no likes ice cream.", correction: "He doesn't like ice cream."},
            {id: '1', sentence: "She goed to the store.", correction: "She went to the store."},
            {id: '2', sentence: "They plays video games all day.", correction: "They play video games all day."}
        ]
    });

    // Publish the dataset
    await dataset.save();

    // Access a specific example
    const exampleLabel = datasetRef.getRow(2).sentence;
    ```

  </TabItem>
</Tabs>

## Create a `Dataset` from other objects

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
  In Python, `Dataset`s can also be constructed from common Weave objects like [calls](../tracking/tracing.mdx), and Python objects like `pandas.DataFrame`s. This feature is useful if you want to create an example `Dataset` from specific examples.

  ### Weave call

  To create a `Dataset` from one or more Weave calls, retrieve the call object(s), and add them to a list in the `from_calls` method.

  ```python
  @weave.op
  def model(task: str) -> str:
      return f"Now working on {task}"

  res1, call1 = model.call(task="fetch")
  res2, call2 = model.call(task="parse")

  dataset = Dataset.from_calls([call1, call2])
  # Now you can use the dataset to evaluate the model, etc.
  ```

  ### Pandas DataFrame

  To create a `Dataset` from a Pandas `DataFrame` object, use the `from_pandas` method. 

  To convert the `Dataset` back, use `to_pandas`.

  ```python
  import pandas as pd

  df = pd.DataFrame([
      {'id': '0', 'sentence': "He no likes ice cream.", 'correction': "He doesn't like ice cream."},
      {'id': '1', 'sentence': "She goed to the store.", 'correction': "She went to the store."},
      {'id': '2', 'sentence': "They plays video games all day.", 'correction': "They play video games all day."}
  ])
  dataset = Dataset.from_pandas(df)
  df2 = dataset.to_pandas()

  assert df.equals(df2)
  ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
   This feature is not currently available in TypeScript.  Stay tuned!
  </TabItem>
</Tabs>

## Edit and delete a `Dataset` in the UI

:::tip
To follow along with the example screenshots shown in this section, run the code shown in the [`Dataset` quickstart](#dataset-quickstart) and navigate to the **Datasets** tab in the Weave UI.
:::

You can edit and delete existing `Dataset`s from the **Datasets** tab in the UI. To create a `Dataset`, [use one of the SDKs](#dataset-quickstart). 

### Edit a `Dataset` 

1. Navigate to the Weave project containing the `Dataset` you want to edit.
2. From the sidebar, select **Datasets**. Your available `Dataset`s display.

   ![Dataset UI](./imgs/datasetui.png)

3. In the **Object** column, click the name and version of the `Dataset` you want to edit. A pop-out modal showing `Dataset` information like name, version, author, and `Dataset` rows displays.

   ![View `Dataset` information](./imgs/datasetui-popout.png)

4. In the upper right-hand corner of the modal, click the **Edit dataset** button (the pencil icon). An **+ Add row** button displays at the bottom of the modal.

    ![`Dataset` UI- Add row icon](./imgs/datasetui-popout-edit.png)

5. Click **+ Add row**. A green row displays at the top of your existing `Dataset` rows, indicating that you can add a new row to the `Dataset`. 

    ![`Dataset` UI](./imgs/datasetui-popout-edit-green.png)

6. To add data to a new row, click the desired column within that row. The default **id** column in a `Dataset` row cannot be edited, as Weave assigns it automatically upon creation. An editing modal appears with **Text**, **Code**, and **Diff** options for formatting.

    ![`Dataset` UI - Add data to a column and format.](./imgs/datasetui-popout-edit-addcol.png)

7. Repeat step 6 for each column that you want to add data to in the new row. 

    ![`Dataset` UI - Add data to all columns.](./imgs/datasetui-popout-edit-colsadded.png)

8. Repeat step 5 for each row that you want to add to the `Dataset`.

9. Once you're done editing, publish your `Dataset` by clicking **Publish** in the upper right-hand corner of the modal. Alternatively, if you don't want to publish your changes, click **Cancel**. 

    ![`Dataset` UI - Publish or cancel.](./imgs/datasetui-popout-edit-publish.png)

   Once published, the new version of the `Dataset` with updated rows is available in the UI. 

     ![`Dataset` UI - Published metadata.](./imgs/datasetui-popout-edit-published-meta.png)
     ![`Dataset` UI - Published rows.](./imgs/datasetui-popout-edit-published-rows.png)
   
### Delete a `Dataset`

1. Navigate to the Weave project containing the `Dataset` you want to edit.
2. From the sidebar, select **Datasets**. Your available `Dataset`s display.
3. In the **Object** column, click the name and version of the `Dataset` you want to delete. A pop-out modal showing `Dataset` information like name, version, author, and `Dataset` rows displays.

4. In the upper right-hand corner of the modal, click the trash can icon. 

   ![`Dataset` UI - Delete a `Dataset` icon.](./imgs/dataset-trashcan.png)

   A pop-up modal prompting you to confirm `Dataset` deletion displays. 

   ![`Dataset` UI - Confirm deletion modal.](./imgs/datasetui-delete-modal.png)

5. In the pop-up modal, click the red **Delete** button to delete the `Dataset`. Alternatively, click **Cancel** if you don't want to delete the `Dataset`. 

   Now, the `Dataset` is deleted, and no longer visible in the **Datasets** tab in your Weave dashboard.