---
sidebar_position: 1
hide_table_of_contents: true
---

# Anthropic

Weave automatically tracks and logs LLM calls made via the [Anthropic Python library](https://github.com/anthropics/anthropic-sdk-python), after `weave.init()` is called.

## Setup

1. Install the Anthropic Python library:
   ```bash
   pip install anthropic weave
   ```

2. Initialize Weave in your Python script:
   ```python
   import weave
   weave.init("my_llm_project")
   ```
   :::note
   We patch the anthropic `Messages.create` method for you to keep track of your LLM calls.
   :::

3. Use Anthropic's python SDK as usual:

    ```python
    import os
    from anthropic import Anthropic

    client = Anthropic(
        # This is the default and can be omitted
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )

    message = client.messages.create(
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": "Hello, Claude",
            }
        ],
        model="claude-3-opus-20240229",
    )
    print(message.content)
    ```

Weave will now track and log all LLM calls made through Anthropic. You can view the logs and insights in the Weave web interface.
