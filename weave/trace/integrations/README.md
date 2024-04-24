<!-- Please generate readme file contents. This readme will cover the details on how to author an integration  -->

# Integrations

This directory contains various integrations for Weave. As of this writing, there are 2 methods of patching: autopatching and manual integration. Furthermore, there are 2 styles of libraries we are interested in patching: model vendors and orchestration frameworks.

**Patch Methods**
_ `autopatching`: autopatching is done automatically for the user when initializing Weave.
_ Notes:
_ we might want to expose an `autopatch` method that can be called indpendent of initialization for better code ergonomics.
_ we will likely (but have not) exposed a way to configure the autopatcher (similar to DataDog's `patch` method) \* `manual`: When patching is not sufficient (or possible), we can expose utilities for the user. For example, with an orchestration framework such as `Langchain`, we will provide a callback to fit into their program architecture more cleanly.

**Library Style**
_ `Model Vendor`: A model vendor is essentially an API that provides inference (eg. OpenAI). Users directly call these APIs. The integration is more simple here since we are just tracking a single call.
_ `Orchestration Framework`: there are many orchestration frameworks emerging (eg. Langchain) that help users compose a more sophisticated GenAI pipeline. In these cases the integration is a bit more complex as we must learn about and handle the specific nuances of the call stack for these frameworks.

## Developing an Integration:

1. Create a folder under with the name of the library/vendor
2. Add the following files:

```
.
├── __init__.py
├── <vendor>.py
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
   res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
   assert len(res.calls) == 1
   ```

4. At this point, you should be able to run the unit test and see a failure at the `assert len(res.calls) == 1` line. If you see any different errors, fix them before moving forward. Note, to run the test, you will likely need a vendor key, for example: `MISTRAL_API_KEY=... pytest trace/integrations/mistral/mistral_test.py::test_mistral_quickstart`
5. Now - time to implement the integration!
