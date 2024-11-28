# Amazon Bedrock

Amazon Bedrock provides easy access to foundation models from providers like Anthropic, AI21 Labs, and Stability AI with a single API. With Weights & Biases (W&B) Weave, you can log, debug, and evaluate your Bedrock models to streamline your LLM application development workflow.

This guide provides an overview of Weave on Bedrock, including:

- [Why you should use Weave on Bedrock](#why-use-weave-on-bedrock).
- The available [integration options](#integration-options)
- [General prerequisites](#general-prerequisites) for using Weave on Bedrock
- Tutorials describing how to use Weave on Bedrock with [`boto3`](#use-boto3) and [`AnthropicBedrock`](#use-the-anthropic-bedrock-python-sdk)

> **Test Weave on Bedrock**
>
> Do you just want to try Weave on Bedrock without any setup? Check out this [Google Colab](https://colab.research.google.com/drive/1-KOjL-jA25nRyMPwKJjMg3jqL51m6J2k?usp=sharing#scrollTo=db351094-c5b7-4194-af04-b4ddc85399c6) that runs through the material covered in the tutorials in this guide, in addition to advanced use cases. 

## Why use Weave on Bedrock

Amazon Bedrock simplifies access to leading foundation models, while Weave helps you:
- **Log and debug**: Keep track of LLM inputs, outputs, and traces for better transparency.
- **Evaluate models**: Build rigorous, direct comparisons between models to identify the best fit for your use case.
- **Organize workflows**: Structure and analyze information from experimentation to production with minimal effort.

## Integration Options

You can integrate Amazon Bedrock with Weave in three primary ways: using `boto3`, a Bedrock-specific SDK like `AnthropicBedrock`, or a general Python package like `litellm`.

### `boto3`

You can use `boto3` to easily test and use all of the LLMs available on Bedrock. However, using `boto3` requires model-specific formatting for requests and responses. 

This option is best if you:
- Need flexibility to work with or test multiple models on Bedrock.
- Are already familiar with `boto3` and other AWS SDKs.

The following example shows how to call Anthropic's Claude 2 model on Bedrock using `boto3`:

```python
import boto3
bedrock_client = boto3.client("bedrock", region_name="us-west-2")

response = bedrock_client.invoke_model(
    model_id="anthropic.claude-2",
    input_text="What is renewable energy?"
)
```

For a full tutorial that describes how to use `boto3` with Weave, see [Use `boto3`](#use-boto3)

### A Bedrock-specific SDK 

Bedrock-specific SDKs like `AnthropicBedrock` offer a stable, native interface with features such as parallel calls. However, this option is currently limited to Anthropic models.

This option is best if you:
- Plan to use specific models exclusively.
- Want a simplified, model-specific SDK for easier integration.

The following example shows how to call Anthropic's Claude 2 model on Bedrock using `AnthropicBedrock`:

```python
from anthropic import AnthropicBedrock

client = AnthropicBedrock(
    aws_access_key="<access key>",
    aws_secret_key="<secret key>",
    aws_session_token="<session_token>",
    aws_region="<region>",
)

message = client.messages.create(
    model="anthropic.claude-3-5-sonnet-20241022-v2:0",
    max_tokens=256,
    messages=[{"role": "user", "content": "What is renewable energy?"}]
)
print(message.content)
```

For a full tutorial that describes how to use `AnthropicBedrock` with Weave, see [Use the Anthropic Bedrock Python SDK](#use-the-anthropic-bedrock-python-sdk).

### An LLM-specific Python package 

The most comprehensive option is to use an LLM-specific Python package like `litellm`, which allows you to work seamlessly with all LLMs on Bedrock, as well as other providers. However, initial setup may require some debugging. 

This option is best if you:

- Want maximum flexibility to integrate Bedrock with multiple providers.
- Need a unified interface for managing multiple LLMs.

The following example shows how to call Anthropic's Claude 2 on Bedrock using LiteLLM.

```python
from litellm import Bedrock

# Initialize the LiteLLM Bedrock client
bedrock_client = Bedrock(
    aws_access_key_id="YOUR_AWS_ACCESS_KEY_ID",
    aws_secret_access_key="YOUR_AWS_SECRET_ACCESS_KEY",
    aws_region="us-west-2"
)

# Define a query
query = "What are the benefits of renewable energy?"

# Call the model
response = bedrock_client.completion(
    model="anthropic.claude-2",
    prompt=query,
    max_tokens=300
)

# Print the response
print(response["output"])
```

## General prerequisites

Before you can get started with Weave on Amazon Bedrock, complete the general prerequisites:

1. [Sign up for a W&B account or log in](https://app.wandb.ai/login?signup=true&_gl=1*bm01gz*_ga*ODEyMjQ4MjkyLjE3MzE0MzU1NjU.*_ga_JH1SJHJQXJ*MTczMjc1Mjk4Ny40NS4xLjE3MzI3NTMzODAuNTYuMC4w*_ga_GMYDGNGKDT*MTczMjc1Mjk4Ny4zNi4xLjE3MzI3NTMzNzYuMC4wLjA.*_gcl_au*OTI3ODM1OTcyLjE3MzE0MzU1NjUuMTI0Mzg5MDMyMy4xNzMxODk0OTk5LjE3MzE4OTQ5OTg.).
2. Complete the [Bedrock prerequisites](https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html).
3. Python 3.8 or later

Next, learn how to use either [`boto3`](#use-boto3) or the [Anthropic Bedrock Python SDK](#use-the-anthropic-bedrock-python-sdk)

## Use `boto3`

### Prerequisites

- The [general Weave on Bedrock prerequisites](#general-prerequisites)
- A terminal application
- A code editor
- The `weave`package
   ```python
   pip install -U weave boto3
   ```
- The [`boto3`](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/quickstart.html#installation) package
- The [AWS CLI](https://docs.aws.amazon.com/cli/v1/userguide/cli-chap-install.html)

### Tutorial 

Once you complete the prerequisites, start logging to Weave.

1. Open to a terminal application.
2. In the terminal, log in to AWS and enter your credentials when prompted. 
    ```python
    aws sso login
    ```
3. Open a code editor.
4. Create a file named `weave-bedrock-boto3.py`
5. In `weave-bedrock-boto3.py`, import `weave`, `json`, `boto3`, `pprint` from `pprint`, `ClientError` from `botocore.exceptions`, and `mprint` from `utils`: 
    ```python
    import weave
    import json
    import boto3
    from pprint import pprint
    from botocore.exceptions import ClientError

    from utils import mprint
    ```
7. Create a Weave project to store your traces.
    ```python
    weave.init('weave-bedrock-boto3-intro')
    ```
8. Decorate your Bedrock call with `@weave.op` to automatically log traces to Weave. 

    ```python
    @weave.op()
    def call_model(
        model_id: str,
        messages: str,
        max_tokens: int=400,
        ) -> dict:

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "messages": messages,
            "max_tokens": max_tokens})

        response = bedrock_client.invoke_model(body=body,modelId=model_id)

        response_body = json.loads(response.get('body').read())
        return response_body

    @weave.op
    def format_prompt(prompt: str) -> list[dict]:
        messages = [{"role": "user",
                    "content": [
                        {"type": "text",
                        "text": prompt}]}]
        return messages

    @weave.op
    def claude(model_id: str, prompt: str, max_tokens: int=400) -> str:
        messages = format_prompt(prompt)
        response_body = call_model(model_id, messages, max_tokens)
        return response_body["content"][0]["text"]

    model_id = 'anthropic.claude-3-5-sonnet-20240620-v1:0'
    user_msg = ("In Bash, how do I list all text files in the current directory "
                "(excluding subdirectories) that have been modified in the last month?")

    outputs = call_model(model_id, user_msg)
    ```

9. Run `weave-bedrock-boto3.py`. When prompted, log in to Weights & Biases, and enter your W&B API key: 
    ```python
    python weave-bedrock-boto3.py
    ```

10. Navigate to your Weave project dashboard. Your LLM app traces automatically log to your Weave project when you run `weave-bedrock-boto3.py`.
   
## Use the Anthropic Bedrock Python SDK 

### Prerequisites

- The [general Weave on Bedrock prerequisites](#general-prerequisites)
- A terminal application.
- An AWS account.
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-welcome.html) version 2.13.23 or newer.
- [Configure your AWS credentials in the command line](https://docs.aws.amazon.com/cli/v1/userguide/cli-chap-configure.html), or find your credentials in **Command line or programmatic access** in your AWS dashboard.
- Verify your credentials:
    ```bash
    aws sts get-caller-identity  
    ```
- Install the Anthropic Bedrock SDK:
    ```python
    pip install -U "anthropic[bedrock]"
    ```

### Tutorial

Once you complete the prerequisites, start logging to Weave.

1. Open a code editor.
2. Create a file named `weave-bedrock-anthropicsdk.py`.
3. In `weave-bedrock-anthropicsdk.py`, import `weave` and `AnthropicBedrock` from `anthropic`
    ```python
    import weave
    from anthropic import AnthropicBedrock
    ```
4. Create a Weave project to store your traces.
    ```python
    weave.init("weave-bedrock-anthropicsdk")    
    ```
5. Decorate your functions with `@weave.op`:

    ```python
    # format_prompt defined in first section
    @weave.op
    def format_prompt(prompt: str) -> list[dict]:
        messages = [{"role": "user",
                    "content": [
                        {"type": "text",
                        "text": prompt}]}]
        return messages

    @weave.op
    def call_claude_bis(prompt: str, model_id: str, max_tokens: int=400) -> str:
        "Call Bedrock Claude using the anthropic Python SDK"
        messages = format_prompt(prompt)
        response_body = client.messages.create(
            model="anthropic.claude-3-5-sonnet-20240620-v1:0",
            max_tokens=256,
            messages=messages)
        return response_body.content[0].text

    model_id = 'anthropic.claude-3-5-sonnet-20240620-v1:0'
    response = call_claude_bis("How do I say: This is really handy, in French?", model_id)
    mprint(response)
    ```