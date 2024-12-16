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

import streamlit as st
import wandb
from openai import OpenAI
from set_env import set_env

import weave

_ = set_env("OPENAI_API_KEY")
_ = set_env("WANDB_API_KEY")

# highlight-next-line
wandb.login()

# highlight-next-line
weave_client = weave.init("feedback-example")

oai_client = OpenAI()


# highlight-next-line
@weave.op
def chat_response(prompt):
    stream = oai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": prompt},
            *[
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ],
        ],
        stream=True,
    )
    response = st.write_stream(stream)
    return {"response": response}


def display_chat_messages():
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            # Only show feedback options for assistant messages
            if message["role"] == "assistant":
                # Get index of this call in the session state
                call_idx = (
                    sum(
                        m["role"] == "assistant"
                        for m in st.session_state.messages[: idx + 1]
                    )
                    - 1
                )

                # Create a container for feedback options
                feedback_container = st.container()
                with feedback_container:
                    col1, col2, col3 = st.columns([1, 1, 4])

                    # Thumbs up button
                    with col1:
                        # highlight-next-line
                        if st.button("👍", key=f"thumbs_up_{idx}"):
                            if "calls" in st.session_state and call_idx < len(
                                st.session_state.calls
                            ):
                                # highlight-next-line
                                st.session_state.calls[call_idx].feedback.add_reaction(
                                    "👍"
                                )
                                st.success("Thanks for the feedback!")

                    # Thumbs down button
                    with col2:
                        # highlight-next-line
                        if st.button("👎", key=f"thumbs_down_{idx}"):
                            if "calls" in st.session_state and call_idx < len(
                                st.session_state.calls
                            ):
                                # highlight-next-line
                                st.session_state.calls[call_idx].feedback.add_reaction(
                                    "👎"
                                )
                                st.success("Thanks for the feedback!")

                    # Text feedback
                    with col3:
                        feedback_text = st.text_input(
                            "Feedback", key=f"feedback_input_{idx}"
                        )
                        if st.button("Submit Feedback", key=f"submit_feedback_{idx}"):
                            if feedback_text and call_idx < len(st.session_state.calls):
                                # highlight-next-line
                                st.session_state.calls[call_idx].feedback.add_note(
                                    feedback_text
                                )
                                st.success("Feedback submitted!")


def show_chat_prompt():
    if prompt := st.chat_input("What is up?"):
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            with weave.attributes(
                {"session": st.session_state["session_id"], "env": "prod"}
            ):
                result, call = chat_response.call(prompt)
                st.write(result["response"])
                st.session_state.messages.append(
                    {"role": "assistant", "content": result["response"]}
                )
                # highlight-next-line
                st.session_state.calls.append(call)


def init_session_state():
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = "123abc"

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "calls" not in st.session_state:
        st.session_state.calls = []


def main():
    st.title("Add feedback")

    init_session_state()
    display_chat_messages()
    show_chat_prompt()

    st.rerun()


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
