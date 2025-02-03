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

### What information does Weave capture for a function?

A function can be designated as a Weave [Op](/guides/tracking/ops) either manually through a decorator or automatically as part of an enabled integration. When an Op executes, Weave captures detailed information to support your analysis. Weave provides you with fine grained control over what is logged in case you would like something different than the default; see below for configuration examples.

- **Code capture** - Weave captures a representation of the Op's source code. This includes inline comments as well as recursively capturing the value of variables or the source of non-Op functions that were called. Code capture allows you to see what your function was doing even if the change was not saved to your source control system. Code capture is used as part of Op versioning, allowing you to understand the evaluation of your code over time. If code capture is disabled, a hash value will be used instead.

- **Function name, inputs, and outputs** - The name of the function will be captured but can be [overridden](/guides/tracking/tracing/#call-display-name). A JSON-based representation of the inputs and outputs will be captured. For inputs, argument name will be capture in addition to value. Weave lets you [customize the logging](/guides/tracking/ops#customize-logged-inputs-and-outputs) of inputs and outputs - you can specify a function to add/remove/modify what is logged.

- **Op call hierarchy** - When an Op is called within the context of another Op executing, this relationship is captured, even in cases
  where there is an intermediate non-Op function executing. This relationship between Op calls is used to provide a "Trace tree".

- **Execution status and exceptions** - Weave tracks whether a function is executing, finished, or errored. If an exception occurs during execution the error message and a stack track is recorded.

- **System information** - Weave may capture information about which operating system the client is running on including detailed version information.

- **Client information** - Weave may capture information about the Weave client itself, such as the programming language in use and detailed version information for that language and the Weave client library.

- **Timing** - The execution start and end time is captured and also used for latency calculations.

- **Token usage** - In some [integrations](/guides/integrations/) LLM token usage counts may be automatically logged.

- **User and run context** - Logging is associated with a W&B user account. That will be captured along with any wandb Run context.

- **Derived information** - Weave may compute derived information from the raw information logged, for example a cost estimate may be calculated based on token usage and knowledge of the model used. Weave also aggregates some information over calls.

- **Additional information you choose** - You can choose to log [custom attributes](/guides/core-types/models#track-production-calls) as part of your call or attach [feedback](/guides/tracking/feedback#add-feedback-to-a-call) to a call.

### How can I disable code capture?

You can disable code capture during Weave client initialization: `weave.init("entity/project", settings={"capture_code": False})`.
You can also use the [environment variable](/guides/core-types/env-vars) `WEAVE_CAPTURE_CODE=false`.

### How can I disable system information capture?

You can disable system information capture during Weave client initialization: `weave.init("entity/project", settings={"capture_system_info": False})`.

### How can I disable client information capture?

You can disable client information capture during Weave client initialization: `weave.init("entity/project", settings={"capture_client_info": False})`.

### Will Weave affect my function's execution speed?

The overhead of Weave logging is typically negligible compared to making a call to an LLM.
To minimize Weave's impact on the speed of your Op's execution, its network activity happens on a background thread.
When your program is exiting it may appear to pause while any remaining enqueued data is logged.
