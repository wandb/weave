# Playground

Evaluating LLM prompts and responses is challenging. The Playground tool enables you to quickly iterate on prompts: editing, retrying, and deleting messages. The LLM Playground is currently in preview.

There are two ways to access the Playground:

1. From the sidebar, click **Playground**. This will open a fresh Playground page with a simple system prompt.
2. From the Call page, click the **Open chat in playground** button from the call page's chat view.

![Screenshot of Open in Playground button](imgs/open_chat_in_playground.png)

## Retry, edit, and delete messages

Once in the Playground, you can see the chat history.
When hovering over a message, you will see three buttons: **Edit**, **Retry**, and **Delete**.

![Screenshot of Playground message buttons](imgs/playground_message_buttons.png)

1. **Retry**: Deletes all subsequent messages and retries the chat from the selected message.
2. **Delete**: Removes the message from the chat.
3. **Edit**: Allows you to modify the message content.

![Screenshot of Playground editing](imgs/playground_message_editor.png)

## Adding new messages

To add a new message to the chat without sending it to the LLM, select the role (e.g., **User**) and click **Add**.
To send a new message to the LLM, click the **Send** button or press **Command + Enter**.

![Screenshot of Playground sending a message](imgs/playground_chat_input.png)

## Configuring the LLM

We currently support 4 LLM providers.
To use each LLM, your team admin needs to add the relevant API key to your team's settings (found at **wandb.ai/[team-name]/settings**):

- OpenAI: `OPENAI_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY`
- Gemini: `GOOGLE_API_KEY`
- Groq: `GEMMA_API_KEY`

### Choosing the LLM and its settings

Click the **Settings** button to open the settings drawer.

![Screenshot of Playground settings](imgs/playground_settings.png)

You can also switch the LLM using the dropdown menu in the top left.
