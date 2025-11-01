<!-- Please generate readme file contents. This readme will cover the details on how to author an integration  -->

# Integrations

This directory contains various integrations for Weave. Weave provides automatic implicit patching for all supported integrations using an import hook mechanism, making integration seamless and effortless. There are 2 styles of libraries we are interested in patching: model vendors and orchestration frameworks.

**Patch Methods**

- `implicit patching` (default): Libraries are automatically patched regardless of when they are imported. An import hook intercepts library imports and applies patches automatically.

  Example:

  ```python
  # Automatic patching - works regardless of import order!

  # Option 1: Import before weave.init()
  import openai
  import weave
  weave.init('my-project')  # OpenAI is automatically patched!

  # Option 2: Import after weave.init()
  import weave
  weave.init('my-project')
  import anthropic  # Automatically patched via import hook!
  ```

- `explicit patching`: Users can optionally call patch functions after `weave.init()` for fine-grained control over which integrations are enabled.

  Example:

  ```python
  import weave
  weave.init("my-project")
  weave.integrations.patch_openai()  # Manually patch if needed
  ```

- `manual integration`: For frameworks where patching is not sufficient (or possible), we provide utilities like callbacks. For example, with orchestration frameworks such as `Langchain`, we provide a callback to fit into their program architecture more cleanly.

**Library Style**

- `Model Vendor`: A model vendor is essentially an API that provides inference (eg. OpenAI). Users directly call these APIs. The integration is more simple here since we are just tracking a single call.
- `Orchestration Framework`: there are many orchestration frameworks emerging (eg. Langchain) that help users compose a more sophisticated GenAI pipeline. In these cases the integration is a bit more complex as we must learn about and handle the specific nuances of the call stack for these frameworks.

## Using Integrations

### Automatic Implicit Patching (Default)

By default, Weave automatically patches all supported integrations using an import hook mechanism. This works regardless of import order:

```python
import weave
import openai  # Can import before or after weave.init()

weave.init("my-project")  # Integrations are automatically patched!

# Use libraries as normal - they will be traced automatically
client = openai.OpenAI()
response = client.chat.completions.create(...)  # Automatically traced!
```

The import hook uses Python's `sys.meta_path` to intercept imports and automatically apply patches when supported libraries are imported, ensuring seamless integration tracking without requiring manual patch calls.

### Disabling Implicit Patching

If you prefer explicit control over which integrations are patched, you can disable implicit patching:

```python
# Via settings parameter
weave.init('my-project', settings={'implicitly_patch_integrations': False})

# Or via environment variable
# export WEAVE_IMPLICITLY_PATCH_INTEGRATIONS=false
```

When disabled, you must explicitly call patch functions to enable tracing:

```python
import weave

# Initialize with implicit patching disabled
weave.init("my-project", settings={'implicitly_patch_integrations': False})

# Explicitly enable specific integrations
weave.integrations.patch_openai()     # Enable OpenAI tracing
weave.integrations.patch_anthropic()  # Enable Anthropic tracing
weave.integrations.patch_mistral()    # Enable Mistral tracing
# ... etc

# Now use the libraries as normal - they will be traced
from openai import OpenAI
client = OpenAI()
response = client.chat.completions.create(...)  # This will be traced
```

### Available Patch Functions

All integrations have corresponding patch functions for explicit control when needed: `patch_openai()`, `patch_anthropic()`, `patch_mistral()`, etc. These can be used even when implicit patching is enabled for manual control or to re-apply patches.

## Developing a Vendor Integration

When developing a new integration, it will automatically work with both implicit and explicit patching if you follow these guidelines.

1. Create a folder under `weave/integrations/` with the name of the library/vendor
2. Add the following files:

```
.
├── __init__.py
├── <vendor>_sdk.py
└── <vendor>_test.py
```

3. Create a unit test to validate correctness. (Note: it might be easier to copy `mistral_test.py` as an example. However, here are some steps)

   1. At the top of the test file, add a fixture placeholder that will perform the patch for the test.

   ```
   import pytest
   import weave
   from weave.trace_server import trace_server_interface as tsi
   from typing import Generator

   @pytest.fixture()
   def patch_<vendor>() -> Generator[None, None, None]:
       print("TODO: Implement")
   ```

   2. Create your first test function. There are a few components:
      - `pytest.mark.vcr` - this is a utility that will allow you to capture the vendor's network requests locally, and save it for unit tests later. The library we use is `pytest-recording` which uses `vcrpy`. Read those docs to learn more!
      - `client: weave.weave_client.WeaveClient`. This tells the system to use a fake `W&B Trace Server` for the tests
      - `patch_<vendor>`. This will automatically call the above patch function to facilitate the patching.

   ```
   @pytest.mark.vcr(
       filter_headers=["authorization"],
       allowed_hosts=["api.wandb.ai", "localhost"],
   )
   def test_<vendor>_quickstart(
       client: weave.weave_client.WeaveClient,
       patch_<vendor>: None,
   ) -> None:
       ...
   ```

   3. Typically the vendor has a "getting started" example. Copy that (or create your own) in place of the `...`.
      - Replace any API key fetching with something like `api_key = os.environ.get("<VENDOR>_API_KEY", "DUMMY_API_KEY")`. This will make sure we use the environment variable when available, but then a dummy key in true unit tests.
   4. Add any assertions to validate correct logging. The base case to validate that a call was logged would be:

   ```
   calls = list(client.get_calls())
   assert len(calls) == 1
   ```

4. At this point, you should be able to run the unit test and see a failure at the `assert len(calls) == 1` line. If you see any different errors, fix them before moving forward. Note, to run the test, you will likely need a vendor key, for example: `MISTRAL_API_KEY=... pytest --record-mode=rewrite weave/integrations/mistral/mistral_test.py::test_mistral_quickstart`. Note: the `--record-mode=rewrite` tells the system to ignore any recorded network calls.
5. Now - time to implement the integration!
6. Inside of `<vendor>_sdk.py`, implement the integration. The most basic form will look like this. The key idea is to have a function called `get_<vendor>_patcher` that returns a Patcher object. _Note: this assumes non-generator return libraries. More work is required for those to work well._

   ```python
   import importlib
   from typing import Optional

   import weave
   from weave.integrations.patcher import SymbolPatcher, MultiPatcher, NoOpPatcher
   from weave.trace.autopatch import IntegrationSettings

   _<vendor>_patcher: Optional[MultiPatcher] = None

   def get_<vendor>_patcher(
       settings: Optional[IntegrationSettings] = None,
   ) -> MultiPatcher | NoOpPatcher:
       if settings is None:
           settings = IntegrationSettings()

       if not settings.enabled:
           return NoOpPatcher()

       global _<vendor>_patcher
       if _<vendor>_patcher is not None:
           return _<vendor>_patcher

       base = settings.op_settings
       # Configure settings for the operation
       op_settings = base.model_copy(
           update={"name": base.name or "<vendor>.operation_name"}
       )

       _<vendor>_patcher = MultiPatcher(
           [
               SymbolPatcher(
                   lambda: importlib.import_module(<import_path>),  # Base module import
                   <path_to_symbol>,                                # Path to the target symbol
                   weave.op(**op_settings.model_dump()),           # Wrapper with settings
               )
           ]
       )

       return _<vendor>_patcher
   ```

   Please see the mistral example for how to write an accumulator to work with streaming results.

7. Register the patch function to enable both implicit and explicit patching. Navigate to `weave/integrations/patch.py` and add a new patch function:

   ```python
   def patch_<vendor>(settings: Optional[IntegrationSettings] = None) -> None:
       """Enable Weave tracing for <Vendor>.

       When implicit patching is enabled (default), this is called automatically
       when the <vendor> library is imported. It can also be called explicitly
       after `weave.init()` for manual control.

       Example:
           # Automatic (implicit patching enabled by default):
           import weave
           weave.init("my-project")
           import <vendor>  # Automatically patched!

           # Manual (explicit patching):
           import weave
           weave.init("my-project", settings={'implicitly_patch_integrations': False})
           weave.integrations.patch_<vendor>()
       """
       from weave.integrations.<vendor>.<vendor>_sdk import get_<vendor>_patcher

       if settings is None:
           settings = IntegrationSettings()
       get_<vendor>_patcher(settings).attempt_patch()
   ```

   Note: Once registered here, your integration will automatically work with implicit patching. The import hook will call this function when the vendor library is imported.

8. Add the integration settings to `weave/trace/autopatch.py` in the `AutopatchSettings` class:

   ```python
   class AutopatchSettings(BaseModel):
       # ... existing fields ...
       <vendor>: IntegrationSettings = Field(default_factory=IntegrationSettings)
   ```

   This allows users to configure the integration via settings if needed.

9. Next, add the patcher to the test. Inside of `patch_<vendor>` fixture, fill out:

   ```python
   @pytest.fixture()
   def patch_<vendor>() -> Generator[None, None, None]:
       from weave.integrations.<vendor>.<vendor>_sdk import get_<vendor>_patcher

       patcher = get_<vendor>_patcher()
       patcher.attempt_patch()
       yield
       patcher.undo_patch()
   ```

10. Now, run the unit test again, for example: `MISTRAL_API_KEY=... pytest --record-mode=rewrite weave/integrations/mistral/mistral_test.py::test_mistral_quickstart`. If everything worked, you should now see a PASSING test!

    - Optional: if you want to see this in the UI, run `MISTRAL_API_KEY=... pytest --trace-server=prod --record-mode=rewrite weave/integrations/mistral/mistral_test.py::test_mistral_quickstart` (notice the `--trace-server=prod`). This tells the system to target prod so you can actually see the results of your integration in the UI and make sure everything looks good.

11. Finally, when you are ready, save the network recordings:
    - Run `MISTRAL_API_KEY=... pytest --record-mode=rewrite weave/integrations/mistral/mistral_test.py::test_mistral_quickstart` to generate the recording
    - Run `MISTRAL_API_KEY=... pytest weave/integrations/mistral/mistral_test.py::test_mistral_quickstart` to validate it works!
12. Export the patch function from `weave/integrations/__init__.py`:
    ```python
    from weave.integrations.patch import patch_<vendor>
    ```
13. Add your integration to the docs (TBD best practices)!
