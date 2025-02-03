---
title: Log Feedback from Production
---


:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/feedback_prod.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/feedback_prod.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::



<!--- @wandbcode{feedback-colab} -->


It is often hard to automatically evaluate a generated LLM response so, depending on your risk tolerance, you can gather direct user feedback to find areas to improve.

In this tutorial, we'll use a custom chatbot as an example app from which to collect user feedback.
We'll use Streamlit to build the interface and we'll capture the LLM interactions and feedback in Weave.

## Setup


```python
!pip install weave openai streamlit wandb
!pip install set-env-colab-kaggle-dotenv -q # for env var
```


```python
# Add a .env file with your OpenAI and WandB API keys
from set_env import set_env

_ = set_env("OPENAI_API_KEY")
_ = set_env("WANDB_API_KEY")
```

Next, create a file called `chatbot.py` with the following contents:


```python
# chatbot.py

import openai
import streamlit as st
import wandb
from set_env import set_env

import weave

_ = set_env("OPENAI_API_KEY")
_ = set_env("WANDB_API_KEY")

# highlight-next-line
wandb.login()

# highlight-next-line
weave_client = weave.init("feedback-example")
oai_client = openai.OpenAI()


def init_states():
    """Set up session_state keys if they don't exist yet."""
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "calls" not in st.session_state:
        st.session_state["calls"] = []
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = "123abc"


# highlight-next-line
@weave.op
def chat_response(full_history):
    """
    Calls the OpenAI API in streaming mode given the entire conversation history so far.
    full_history is a list of dicts: [{"role":"user"|"assistant","content":...}, ...]
    """
    stream = oai_client.chat.completions.create(
        model="gpt-4", messages=full_history, stream=True
    )
    response_text = st.write_stream(stream)
    return {"response": response_text}


def render_feedback_buttons(call_idx):
    """Renders thumbs up/down and text feedback for the call."""
    col1, col2, col3 = st.columns([1, 1, 4])

    # Thumbs up button
    with col1:
        if st.button("👍", key=f"thumbs_up_{call_idx}"):
            st.session_state.calls[call_idx].feedback.add_reaction("👍")
            st.success("Thanks for the feedback!")

    # Thumbs down button
    with col2:
        if st.button("👎", key=f"thumbs_down_{call_idx}"):
            st.session_state.calls[call_idx].feedback.add_reaction("👎")
            st.success("Thanks for the feedback!")

    # Text feedback
    with col3:
        feedback_text = st.text_input("Feedback", key=f"feedback_input_{call_idx}")
        if st.button("Submit Feedback", key=f"submit_feedback_{call_idx}"):
            if feedback_text:
                st.session_state.calls[call_idx].feedback.add_note(feedback_text)
                st.success("Feedback submitted!")


def display_old_messages():
    """Displays the conversation stored in st.session_state.messages with feedback buttons"""
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            # If it's an assistant message, show feedback form
            if message["role"] == "assistant":
                # Figure out index of this assistant message in st.session_state.calls
                assistant_idx = (
                    len(
                        [
                            m
                            for m in st.session_state.messages[: idx + 1]
                            if m["role"] == "assistant"
                        ]
                    )
                    - 1
                )
                # Render thumbs up/down & text feedback
                if assistant_idx < len(st.session_state.calls):
                    render_feedback_buttons(assistant_idx)


def display_chat_prompt():
    """Displays the chat prompt input box."""
    if prompt := st.chat_input("Ask me anything!"):
        # Immediately render new user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Save user message in session
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Prepare chat history for the API
        full_history = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in st.session_state.messages
        ]

        with st.chat_message("assistant"):
            # Attach Weave attributes for tracking of conversation instances
            with weave.attributes(
                {"session": st.session_state["session_id"], "env": "prod"}
            ):
                # Call the OpenAI API (stream)
                result, call = chat_response.call(full_history)

                # Store the assistant message
                st.session_state.messages.append(
                    {"role": "assistant", "content": result["response"]}
                )

                # Store the weave call object to link feedback to the specific response
                st.session_state.calls.append(call)

                # Render feedback buttons for the new message
                new_assistant_idx = (
                    len(
                        [
                            m
                            for m in st.session_state.messages
                            if m["role"] == "assistant"
                        ]
                    )
                    - 1
                )

                # Render feedback buttons
                if new_assistant_idx < len(st.session_state.calls):
                    render_feedback_buttons(new_assistant_idx)


def main():
    st.title("Chatbot with immediate feedback forms")
    init_states()
    display_old_messages()
    display_chat_prompt()


if __name__ == "__main__":
    main()
```

You can run this with `streamlit run chatbot.py`.

Now, you can interact with this application and click the feedback buttons after each response. 
Visit the Weave UI to see the attached feedback.

## Explanation

If we consider our decorated prediction function as:


```python
import weave

weave.init("feedback-example")


# highlight-next-line
@weave.op
def predict(input_data):
    # Your prediction logic here
    some_result = "hello world"
    return some_result
```

We can use it as usual to deliver some model response to the user:


```python
with weave.attributes(
    {"session": "123abc", "env": "prod"}
):  # attach arbitrary attributes to the call alongside inputs & outputs
    result = predict(input_data="your data here")  # user question through the App UI
```

To attach feedback, you need the `call` object, which is obtained by using the `.call()` method *instead of calling the function as normal*:


```python
result, call = predict.call(input_data="your data here")
```

This call object is needed for attaching feedback to the specific response.
After making the call, the output of the operation is available using `result` above.


```python
call.feedback.add_reaction("👍")  # user reaction through the App UI
```

## Conclusion

In this tutorial, we built a chat UI with Streamlit which had inputs & outputs captured in Weave, alongside 👍👎 buttons to capture user feedback. 
