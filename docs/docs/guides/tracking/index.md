# Tracing

Weave provides powerful tracing capabilities to track and version objects and function calls in your applications. This comprehensive system enables better monitoring, debugging, and iterative development of AI-powered applications, allowing you to "track insights between commits."

## Key Tracing Features

Weave's tracing functionality comprises three main components:

### Calls

[Calls](/guides/tracking/tracing) trace function calls, inputs, and outputs, enabling you to:

- Analyze data flow through your application
- Debug complex interactions between components
- Optimize application performance based on call patterns

### Ops

[Ops](/guides/tracking/ops) are automatically versioned and tracked functions (which produce Calls) that allow you to:

- Monitor function performance and behavior
- Maintain a record of function modifications
- Ensure experiment reproducibility

### Objects

[Objects](/guides/tracking/objects) form Weave's extensible serialization layer, automatically versioning runtime objects (often the inputs and outputs of Calls). This feature allows you to:

- Track changes in data structures over time
- Maintain a clear history of object modifications
- Easily revert to previous versions when needed

By leveraging these tracing capabilities, you can gain deeper insights into your application's behavior, streamline your development process, and build more robust AI-powered systems.

## FAQs

For answers to common questions about Weave tracing, see the [FAQs page](./faqs.md)
