# Playground

> **The LLM Playground is currently in preview.**

Evaluating LLM prompts and responses is challenging. The Weave Playground is designed to simplify the process of iterating on LLM prompts and responses, making it easier to experiment with different models and prompts. With features like prompt editing, message retrying, and model comparison, Playground helps you to quickly test and improve your LLM applications. Playground currently supports OpenAI, Anthropic, Gemini, and Groq.

## Features

- **Quick access:** Open the Playground from the W&B sidebar for a fresh session or from the Call page to test an existing project.
- **Message controls:** Edit, retry, or delete messages directly within the chat.
- **Flexible messaging:** Add new messages as either user or system inputs, and send them to the LLM.
- **Customizable settings:** Configure your preferred LLM provider and adjust model settings.
- **Multi-LLM support:** Switch between models, with team-level API key management.
- **Compare models:** Compare how different models respond to prompts.

Get started with the Playground to optimize your LLM interactions and streamline your prompt engineering process and LLM application development.

- [Prerequisites](#prerequisites)
   - [Add provider credentials and information](#add-provider-credentials-and-information)
   - [Access the Playground](#access-the-playground)
- [Select an LLM](#select-an-llm)
- [Adjust LLM parameters](#adjust-llm-parameters)
- [Add a function](#add-a-function) 
- [Retry, edit, and delete messages](#retry-edit-and-delete-messages)
- [Add a new message](#add-a-new-message)
- [Compare LLMs](#compare-llms)

## Prerequisites

Before you can use Playground, you must [add provider credentials](#add-provider-credentials-and-information), and [open the Playground UI](#access-the-playground). 

### Add provider credentials and information 

Playground currently supports OpenAI, Anthropic, Gemini, Groq, and Amazon Bedrock models.
To use one of the available models, add the appropriate information to your team secrets in W&B settings.

- OpenAI: `OPENAI_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY`
- Gemini: `GOOGLE_API_KEY`
- Groq: `GEMMA_API_KEY`
- Amazon Bedrock:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_REGION_NAME`

### Access the Playground

There are two ways to access the Playground:

1. *Open a fresh Playground page with a simple system prompt*: In the sidebar, select **Playground**. Playground opens in the same tab.
2. *Open Playground for a specific call*: 
    1. In the sidebar, select the **Traces** tab. A list of traces displays.
    2. In the list of traces, click the name of the call that you want to view. The call's details page opens.
    3. Click **Open chat in playground**. Playground opens in a new tab.

![Screenshot of Open in Playground button](imgs/open_chat_in_playground.png)

## Select an LLM

You can switch the LLM using the dropdown menu in the top left. The available models from various providers are listed below:

- [AI21](#ai21)
- [Amazon](#amazon)
- [Anthropic](#anthropic)
- [Cohere](#cohere)
- [Google](#google)
- [Groq](#groq)
- [Meta](#meta)
- [Mistral](#mistral)
- [OpenAI](#openai)
- [X.AI](#xai)


### AI21
- ai21.j2-mid-v1
- ai21.j2-ultra-v1

### Amazon
- amazon.nova-lite
- amazon.nova-micro
- amazon.nova-pro
- amazon.titan-text-express-v1
- amazon.titan-text-lite-v1

### Anthropic
- anthropic.claude-3-5-sonnet-20240620-v1:0
- anthropic.claude-3-haiku-20240307-v1:0
- anthropic.claude-3-opus-20240229-v1:0
- anthropic.claude-3-sonnet-20240229-v1:0
- anthropic.claude-instant-v1
- anthropic.claude-v2
- anthropic.claude-v2:1
- claude-3-5-sonnet-20241022
- claude-3-haiku-20240307
- claude-3-opus-20240229
- claude-3-sonnet-20240229

### Cohere
- cohere.command-light-text-v14
- cohere.command-r-plus-v1:0
- cohere.command-r-v1:0
- cohere.command-text-v14

### Google
- gemini/gemini-1.5-flash
- gemini/gemini-1.5-flash-001
- gemini/gemini-1.5-flash-002
- gemini/gemini-1.5-flash-8b-exp-0827
- gemini/gemini-1.5-flash-8b-exp-0924
- gemini/gemini-1.5-flash-exp-0827
- gemini/gemini-1.5-flash-latest
- gemini/gemini-1.5-pro
- gemini/gemini-1.5-pro-001
- gemini/gemini-1.5-pro-002
- gemini/gemini-1.5-pro-exp-0801
- gemini/gemini-1.5-pro-exp-0827
- gemini/gemini-1.5-pro-latest
- gemini/gemini-pro

### Groq
- groq/gemma-7b-it
- groq/gemma2-9b-it
- groq/llama-3.1-70b-versatile
- groq/llama-3.1-8b-instant
- groq/llama3-70b-8192
- groq/llama3-8b-8192
- groq/llama3-groq-70b-8192-tool-use-preview
- groq/llama3-groq-8b-8192-tool-use-preview
- groq/mixtral-8x7b-32768

### Meta
- meta.llama2-13b-chat-v1
- meta.llama2-70b-chat-v1
- meta.llama3-1-405b-instruct-v1:0
- meta.llama3-1-70b-instruct-v1:0
- meta.llama3-1-8b-instruct-v1:0
- meta.llama3-70b-instruct-v1:0
- meta.llama3-8b-instruct-v1:0

### Mistral
- mistral.mistral-7b-instruct-v0:2
- mistral.mistral-large-2402-v1:0
- mistral.mistral-large-2407-v1:0
- mistral.mixtral-8x7b-instruct-v0:1

### OpenAI
- gpt-3.5-turbo
- gpt-3.5-turbo-0125
- gpt-3.5-turbo-1106
- gpt-3.5-turbo-16k
- gpt-4
- gpt-4-0125-preview
- gpt-4-0314
- gpt-4-0613
- gpt-4-1106-preview
- gpt-4-32k-0314
- gpt-4-turbo
- gpt-4-turbo-2024-04-09
- gpt-4-turbo-preview
- gpt-40-2024-05-13
- gpt-40-2024-08-06
- gpt-40-mini
- gpt-40-mini-2024-07-18
- gpt-4o
- o1-mini
- o1-mini-2024-09-12
- o1-preview
- o1-preview-2024-09-12

### X.AI
- xai/grok-beta


## Adjust LLM parameters

You can experiment with different parameter values for your selected model. To adjust parameters, do the following:

1. In the upper right corner of the Playground UI, click **Chat settings** to open the parameter settings dropdown.
2. In the dropdown, adjust parameters as desired. You can also toggle Weave call tracking on or off, and [add a function](#add-a-function).
3. Click **Chat settings** to close the dropdown and save your changes. 

![Screenshot of Playground settings](imgs/playground_settings.png)

## Add a function

You can test how different models use functions based on input it receives from the user. To add a function for testing in Playground, do the following:

1. In the upper right corner of the Playground UI, click **Chat settings** to open the parameter settings dropdown.
2. In the dropdown, click **+ Add function**.
3. In the pop-up, add your function information.
4. To save your changes and close the function pop-up, click the **x** in the upper right corner.
3. Click **Chat settings** to close the settings dropdown and save your changes.

## Retry, edit, and delete messages

With Playground, you can retry, edit, and delete messages. To use this feature,  hover over the message you want to edit, retry, or delete. Three buttons display: **Delete**, **Edit**, and **Retry**.

- **Delete**: Remove the message from the chat.
- **Edit**: Modify the message content.
- **Retry**: Delete all subsequent messages and retry the chat from the selected message.

![Screenshot of Playground message buttons](imgs/playground_message_buttons.png)
![Screenshot of Playground editing](imgs/playground_message_editor.png)

## Add a new message

To add a new message to the chat, do the following:

1. In the chat box, select one of the available roles (**Assistant** or **User**)
2. Click **+ Add**.
3. To send a new message to the LLM, click the **Send** button. Alternatively, press the **Command** and **Enter** keys.

![Screenshot of Playground sending a message](imgs/playground_chat_input.png)

## Compare LLMs

Playground allows you to compare LLMs. To perform a comparison, do the following:

1. In the Playground UI, click **Compare**. A second chat opens next to the original chat.
2. In the second chat, you can:
   - [Select the LLM to compare](#select-an-llm)
   - [Adjust parameters](#adjust-llm-parameters)
   - [Add functions](#add-a-function)
3. In the message box, enter a message that you want to test with both models and press **Send**.
