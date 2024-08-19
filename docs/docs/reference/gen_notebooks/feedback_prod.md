---
title: Log Feedback from Production
---


:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/feedback_prod.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/feedback_prod.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::



<img src="http://wandb.me/logo-im-png" width="400" alt="Weights & Biases" />
<!--- @wandbcode{feedback-colab} -->


It is often hard to automatically evaluate a generated LLM response so, depending on your risk tolerance, you can gather direct user feedback to use to find areas to improve.

In this tutorial, we'll use a custom RAG chatbot as an example app with which the users can interact and which allows us to collect user feedback.
We'll use Streamlit to build the interface and we'll capture the LLM interactions and feedback in Weave.

## Setup


```python
!pip install weave openai streamlit
```

First, create a file called `secrets.toml` and add an OpenAI key so it works with `[st.secrets](https://docs.streamlit.io/develop/api-reference/connections/st.secrets)`. You can [sign up](https://platform.openai.com/signup) on the OpenAI platform to get your own API key. 


```python
# secrets.toml
OPENAI_API_KEY = "your OpenAI key"
```

Next, create a file called `chatbot.py` with the following contents:


```python
# chatbot.py

import weave
from openai import OpenAI
import streamlit as st

st.title("Add feedback")

# highlight-next-line
@weave.op
def chat_response(prompt):
    stream = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": prompt},
            *[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
        ],
        stream=True,
    )
    response = st.write_stream(stream)
    return {'response': response}

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
# highlight-next-line
weave_client = weave.init('feedback-example')


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
            with weave.attributes({'session': st.session_state['session_id']}):
                result, call = chat_response.call(prompt) # call the function with `.call`, this returns a tuple with a new Call object
# highlight-next-line
                st.button(":thumbsup:",   on_click=lambda: call.feedback.add_reaction("👍"), key='up')
# highlight-next-line
                st.button(":thumbsdown:", on_click=lambda: call.feedback.add_reaction("👎"), key='down')
                st.session_state.messages.append({"role": "assistant", "content": result['response']})

def init_chat_history():
    if "messages" not in st.session_state:
        st.session_state.messages = st.session_state.messages = []


def main():
    st.session_state['session_id'] = '123abc'
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

We can use it as usal to deliver some model response to the user:



```python

import weave
weave.init('feedback-example')
# highlight-next-line
@weave.op
def predict(input_data):
    # Your prediction logic here
    some_result = 'hello world'
    return some_result
```

    /Users/scottcondron/miniconda3/envs/weave/lib/python3.11/site-packages/tqdm/auto.py:21: TqdmWarning: IProgress not found. Please update jupyter and ipywidgets. See https://ipywidgets.readthedocs.io/en/stable/user_install.html
      from .autonotebook import tqdm as notebook_tqdm


    weave version 0.50.14 is available!  To upgrade, please run:
     $ pip install weave --upgrade
    Logged in as Weights & Biases user: _scott.
    View Weave data at https://wandb.ai/_scott/feedback-example/weave


We can use it as usal to deliver some model response to the user:


```python
result = predict(input_data="your data here") # user question through the App UI
```

    🍩 https://wandb.ai/_scott/feedback-example/r/call/ad3464ae-2c75-4034-a027-8bae26825895


To attach feedback, you need the `call` object, which is obtained by using the `.call()` method *instead of calling the function as normal*:


```python
result, call = predict.call(input_data="your data here")
```

    🍩 https://wandb.ai/_scott/feedback-example/r/call/187af172-ca3f-4d41-aa54-065a999f406f


This call object is needed for attaching feedback to the specific response.
After making the call, the output of the operation is available using `result` above.


```python
call.feedback.add_reaction("👍") # user reaction through the App UI
```




    '01916b30-7071-76a3-b23c-55c05c16b565'



## Retrieving Feedback 


```python
thumbs_down = client.feedback(reaction="👎")
calls = thumbs_down.refs().calls()
for call in calls:
    print(call.inputs)
    print(call.feedback)
```

## Conclusion

In this tutorial, we built a chat UI with Streamlit which had inputs & outputs captured in Weave, alongside 👍👎 buttons to capture user feedback.
