# Amazon Bedrock

import DefaultEntityNote from '../../../src/components/DefaultEntityNote.mdx';

Weave automatically tracks and logs LLM calls made via Amazon Bedrock, AWS's fully managed service that offers foundation models from leading AI companies through a unified API.

There are multiple ways to log LLM calls to Weave from Amazon Bedrock. You can use `weave.op` to create reusable operations for tracking any calls to a Bedrock model. Optionally, if you're using Anthropic models, you can use Weave’s built-in integration with Anthropic. 

:::tip
For the latest tutorials, visit [Weights & Biases on Amazon Web Services](https://wandb.ai/site/partners/aws/).
:::

## Traces

Weave will automatically capture traces for Bedrock API calls after you initialize Weave and patch the client.

To use the Bedrock API:

```python
import weave
import boto3
import json
from weave.integrations.bedrock.bedrock_sdk import patch_client

weave.init("my_bedrock_app")

# Create and patch the Bedrock client
client = boto3.client("bedrock-runtime")
patch_client(client)

# Use the client as usual
response = client.invoke_model(
    modelId="anthropic.claude-3-5-sonnet-20240620-v1:0",
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 100,
        "messages": [
            {"role": "user", "content": "What is the capital of France?"}
        ]
    }),
    contentType='application/json',
    accept='application/json'
)
response_dict = json.loads(response.get('body').read())
print(response_dict["content"][0]["text"])
```

<DefaultEntityNote />

To use the `converse` API:

```python
messages = [{"role": "user", "content": [{"text": "What is the capital of France?"}]}]

response = client.converse(
    modelId="anthropic.claude-3-5-sonnet-20240620-v1:0",
    system=[{"text": "You are a helpful AI assistant."}],
    messages=messages,
    inferenceConfig={"maxTokens": 100},
)
print(response["output"]["message"]["content"][0]["text"])

```

## Wrapping with your own ops

You can create reusable operations using the `@weave.op()` decorator. Here's an example showing both the `invoke_model` and `converse` APIs:

```python
@weave.op
def call_model_invoke(
    model_id: str,
    prompt: str,
    max_tokens: int = 100,
    temperature: float = 0.7
) -> dict:
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    })

    response = client.invoke_model(
        modelId=model_id,
        body=body,
        contentType='application/json',
        accept='application/json'
    )
    return json.loads(response.get('body').read())

@weave.op
def call_model_converse(
    model_id: str,
    messages: str,
    system_message: str,
    max_tokens: int = 100,
) -> dict:
    response = client.converse(
        modelId=model_id,
        system=[{"text": system_message}],
        messages=messages,
        inferenceConfig={"maxTokens": max_tokens},
    )
    return response
```

![](./imgs/bedrock_converse.png)

## Create a `Model` for easier experimentation

You can create a Weave Model to better organize your experiments and capture parameters. Here's an example using the `converse` API:

```python
class BedrockLLM(weave.Model):
    model_id: str
    max_tokens: int = 100
    system_message: str = "You are a helpful AI assistant."

    @weave.op
    def predict(self, prompt: str) -> str:
        "Generate a response using Bedrock's converse API"
        
        messages = [{
            "role": "user",
            "content": [{"text": prompt}]
        }]

        response = client.converse(
            modelId=self.model_id,
            system=[{"text": self.system_message}],
            messages=messages,
            inferenceConfig={"maxTokens": self.max_tokens},
        )
        return response["output"]["message"]["content"][0]["text"]

# Create and use the model
model = BedrockLLM(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    max_tokens=100,
    system_message="You are an expert software engineer that knows a lot of programming. You prefer short answers."
)
result = model.predict("What is the best way to handle errors in Python?")
print(result)
```

This approach allows you to version your experiments and easily track different configurations of your Bedrock-based application.

## Bedrock Invoke Agent

Weave supports tracing Amazon Bedrock Agents through the `bedrock-agent-runtime` service. This allows you to monitor agent conversations, track token usage, and capture the full context of agent interactions.

### Basic Usage

```python
import weave
import boto3
import uuid
from weave.integrations.bedrock import patch_client

# Initialize Weave
weave.init("my_bedrock_agent_app")

# Create and patch the Bedrock Agent Runtime client
bedrock_agent_client = boto3.client('bedrock-agent-runtime')
patch_client(bedrock_agent_client)

# Generate a unique session ID
session_id = str(uuid.uuid4())

# Invoke the agent - this call will be automatically tracked by Weave
response = bedrock_agent_client.invoke_agent(
    agentId="YOUR_AGENT_ID",
    agentAliasId="YOUR_AGENT_ALIAS_ID", 
    sessionId=session_id,
    inputText="What can you help me with?",
    enableTrace=True  # Optional: enables detailed tracing
)

# Process the streaming response
complete_response = ""
for event in response["completion"]:
    if 'chunk' in event and 'bytes' in event['chunk']:
        chunk_text = event['chunk']['bytes'].decode('utf-8')
        complete_response += chunk_text
        print(chunk_text, end='')

print(f"\nComplete response: {complete_response}")
```

### Creating Reusable Operations

You can wrap agent calls in `@weave.op` decorated functions for better organization and reusability:

```python
@weave.op
def invoke_bedrock_agent(
    agent_id: str,
    agent_alias_id: str,
    user_input: str,
    session_id: str = None
) -> str:
    """Invoke a Bedrock agent and return the complete response."""
    
    if session_id is None:
        session_id = str(uuid.uuid4())
    
    response = bedrock_agent_client.invoke_agent(
        agentId=agent_id,
        agentAliasId=agent_alias_id,
        sessionId=session_id,
        inputText=user_input,
        enableTrace=True
    )
    
    # Collect the complete streaming response
    complete_response = ""
    for event in response["completion"]:
        if 'chunk' in event and 'bytes' in event['chunk']:
            chunk_text = event['chunk']['bytes'].decode('utf-8')
            complete_response += chunk_text
    
    return complete_response

# Use the operation
result = invoke_bedrock_agent(
    agent_id="YOUR_AGENT_ID",
    agent_alias_id="YOUR_AGENT_ALIAS_ID",
    user_input="Explain machine learning in simple terms"
)
print(result)
```

### Monitoring and Usage Tracking

Weave automatically captures important metrics from Bedrock Agent calls:

- **Token Usage**: Input and output tokens when available from the agent traces
- **Foundation Model**: The underlying model used by the agent
- **Session Information**: Session IDs for conversation tracking
- **Timing**: Request duration and response times


## Learn more

Learn more about using Amazon Bedrock with Weave

### Try Bedrock in the Weave Playground

Do you want to experiment with Amazon Bedrock models in the Weave UI without any set up? Try the [LLM Playground](../tools/playground.md).

### Report: Compare LLMs on Bedrock for text summarization with Weave

The [Compare LLMs on Bedrock for text summarization with Weave](https://wandb.ai/byyoung3/ML_NEWS3/reports/Compare-LLMs-on-Amazon-Bedrock-for-text-summarization-with-W-B-Weave--VmlldzoxMDI1MTIzNw) report explains how to use Bedrock in combination with Weave to evaluate and compare LLMs for summarization tasks, code samples included.