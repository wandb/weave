# Limits and Expected Behaviors

* For retryable requests, Weave retries requests starting at 1 second after receiving the first error and then doubles the amount of time between attempts up to 5 minutes. Requests timeout after 36 hours.

* Instead of raising exceptions, [`.call()`](../../guides/tracking/tracing#creating-calls) captures exceptions and stores them in the `call.exception`. If you need to raise exceptions during execution, set the [`__should_raise` parameter](../../reference/python-sdk/weave/trace/weave.trace.op#function-call), like this:

    ```python showLineNumbers
    # This raises exceptions
    result, call = foo.call(__should_raise=True)
    ```

* [Dedicated Weave instances](../../guides/platform/weave-self-managed) use a different OpenTelemetry ingress URL. Use `{WANDB_HOST}/traces/otel/v1/traces` to access your traces on a dedicated instance. For example, if your host your instance at `acme.wandb.io`, trace information is accessible at `https://acme.wandb.io/traces/otel/v1/traces`.

* Weave sometimes truncates large trace data objects. This occurs because default trace output is a raw, custom Python object that Weave doesn’t know how to serialize. To return all of your trace data, define a dictionary of strings, like this: 

    ```python
    import weave

    class MyObj:
        def __init__(self, x: int):
            self.x = x

        def __repr__(self):
            return f"MyObj(x={self.x})"

        def to_dict(self):
            return {"x": self.x}

    @weave.op()
    def make_my_obj():
        x = "s" * 10_000
        return MyObj(x)
    ```

