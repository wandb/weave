---
title: Log Feedback from Production
---


:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/feedback_prod.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/feedback_prod.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::



<img src="http://wandb.me/logo-im-png" width="400" alt="Weights & Biases" />
<!--- @wandbcode{feedback-colab} -->


It is often hard to automatically evaluate a generated LLM response so, depending on your risk tolerance, you can gather direct user feedback to find areas to improve.

In this tutorial, we'll use a custom RAG chatbot as an example app with which the users can interact and which allows us to collect user feedback.
We'll use Streamlit to build the interface and we'll capture the LLM interactions and feedback in Weave.

## Setup


```python
!pip install weave openai streamlit
```

First, create a file called `secrets.toml` and add an OpenAI key so it works with [st.secrets](https://docs.streamlit.io/develop/api-reference/connections/st.secrets). You can [sign up](https://platform.openai.com/signup) on the OpenAI platform to get your own API key. 


```python
# secrets.toml
OPENAI_API_KEY = "your OpenAI key"
```

Next, create a file called `chatbot.py` with the following contents:


```python
# chatbot.py

import streamlit as st
from openai import OpenAI

import weave

st.title("Add feedback")


# highlight-next-line
@weave.op
def chat_response(prompt):
    stream = client.chat.completions.create(
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


client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
# highlight-next-line
weave_client = weave.init("feedback-example")


def display_chat_messages():
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def get_and_process_prompt():
    if prompt := st.chat_input("What is up?"):
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            # highlight-next-line
            with weave.attributes(
                {"session": st.session_state["session_id"], "env": "prod"}
            ):
                # This could also be weave model.predict.call if you're using a weave.Model subclass
                result, call = chat_response.call(
                    prompt
                )  # call the function with `.call`, this returns a tuple with a new Call object
                # highlight-next-line
                st.button(
                    ":thumbsup:",
                    on_click=lambda: call.feedback.add_reaction("👍"),
                    key="up",
                )
                # highlight-next-line
                st.button(
                    ":thumbsdown:",
                    on_click=lambda: call.feedback.add_reaction("👎"),
                    key="down",
                )
                st.session_state.messages.append(
                    {"role": "assistant", "content": result["response"]}
                )


def init_chat_history():
    if "messages" not in st.session_state:
        st.session_state.messages = st.session_state.messages = []


def main():
    st.session_state["session_id"] = "123abc"
    init_chat_history()
    display_chat_messages()
    get_and_process_prompt()


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
