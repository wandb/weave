import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Ops

A Weave op is a versioned function that automatically logs all calls.

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    To create an op, decorate a python function with `weave.op()`

    ```python showLineNumbers
    import weave

    @weave.op()
    def track_me(v):
        return v + 5

    weave.init('intro-example')
    track_me(15)
    ```

    Calling an op will create a new op version if the code has changed from the last call, and log the inputs and outputs of the function.

    :::note
    Functions decorated with `@weave.op()` will behave normally (without code versioning and tracking), if you don't call `weave.init('your-project-name')` before calling them.
    :::

    Ops can be [served](/guides/tools/serve) or [deployed](/guides/tools/deploy) using the Weave toolbelt.

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    To create an op, wrap a typescript function with `weave.op`

    ```typescript showLineNumbers
    import * as weave from 'weave'

    function trackMe(v: number) {
        return v + 5
    }

    const trackMeOp = weave.op(trackMe)
    trackMeOp(15)


    // You can also do this inline, which may be more convenient
    const trackMeInline = weave.op((v: number) => v + 5)
    trackMeInline(15)
    ```

  </TabItem>
</Tabs>

## Customize display names

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    You can customize the op's display name by setting the `name` parameter in the `@weave.op` decorator:

    ```python
    @weave.op(name="custom_name")
    def func():
        ...
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

## Customize logged inputs and outputs

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    If you want to change the data that is logged to weave without modifying the original function (e.g. to hide sensitive data), you can pass `postprocess_inputs` and `postprocess_output` to the op decorator.

    `postprocess_inputs` takes in a dict where the keys are the argument names and the values are the argument values, and returns a dict with the transformed inputs.

    `postprocess_output` takes in any value which would normally be returned by the function and returns the transformed output.

    ```py
    from dataclasses import dataclass
    from typing import Any
    import weave

    @dataclass
    class CustomObject:
        x: int
        secret_password: str

    def postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
        return {k:v for k,v in inputs.items() if k != "hide_me"}

    def postprocess_output(output: CustomObject) -> CustomObject:
        return CustomObject(x=output.x, secret_password="REDACTED")

    @weave.op(
        postprocess_inputs=postprocess_inputs,
        postprocess_output=postprocess_output,
    )
    def func(a: int, hide_me: str) -> CustomObject:
        return CustomObject(x=a, secret_password=hide_me)

    weave.init('hide-data-example') # 🐝
    func(a=1, hide_me="password123")
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

## Control sampling rate

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    You can control how frequently an op's calls are traced by setting the `tracing_sample_rate` parameter in the `@weave.op` decorator. This is useful for high-frequency ops where you only need to trace a subset of calls.

     Note that sampling rates are only applied to root calls. If an op has a sample rate, but is called by another op first, then that sampling rate will be ignored.

    ```python
    @weave.op(tracing_sample_rate=0.1)  # Only trace ~10% of calls
    def high_frequency_op(x: int) -> int:
        return x + 1

    @weave.op(tracing_sample_rate=1.0)  # Always trace (default)
    def always_traced_op(x: int) -> int:
        return x + 1
    ```

    When an op's call is not sampled:
    - The function executes normally
    - No trace data is sent to Weave
    - Child ops are also not traced for that call

    The sampling rate must be between 0.0 and 1.0 inclusive.

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet. Stay tuned!
    ```
  </TabItem>
</Tabs>

## Control call link output

If you want to suppress the printing of call links during logging, you can set the `WEAVE_PRINT_CALL_LINK` environment variable to `false`. This can be useful if you want to reduce output verbosity and reduce clutter in your logs.

```bash
export WEAVE_PRINT_CALL_LINK=false
```

## Deleting an op

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    To delete a version of an op, call `.delete()` on the op ref.

    ```python
    weave.init('intro-example')
    my_op_ref = weave.ref('track_me:v1')
    my_op_ref.delete()
    ```

    Trying to access a deleted op will result in an error.

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>
