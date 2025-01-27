# Troubleshooting 

This page provides solutions and guidance for common issues you may encounter. As we continue to expand this guide, more troubleshooting topics will be added to address a broader range of scenarios.

:::tip
Do you have Weave troubleshooting advice to share with the community? Click **Edit this page** at the bottom of this guide to contribute directly by submitting a pull request.
:::

## Trace pages load slowly

If trace pages are loading slowly, reduce the number of rows displayed to improve load time. The default value is `50`. You can either reduce the number of rows via the UI, or using query parameters.

### Adjust via the UI (recommended)

Use the **Per page** control at the bottom-right of the Traces page to adjust the number of rows displayed. In addition to the default of `50`, you can also set to `10`, `25`, or `100`.

### Use query parameters 

If you prefer a manual approach, you can modify the `pageSize` query parameter in your query URL to a value less than the maximum of `100`.