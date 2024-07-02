---
sidebar_position: 2
hide_table_of_contents: true
---

# Tutorial: Collecting Feedback

Gathering feedback from end users of your application is a useful way to get signal on how to improve it. 

In this tutorial, we'll show how to collect feedback from users of your application using Weave. Because collecting feedback is slow and expensive, we'll use the feedback we've collected to build an evaluation dataset which we can use for automated evaluation.

## Getting Started

To start collecting feedback within your application, the first step is to track your function with the @weave.op decorator. Here’s how:

```python
@weave.op
def predict(input_data):
    # Your prediction logic here
    return some_output
```

Once your function is set up as a Weave operation, you can call it as usual:

```python
output = predict(input_data="your data here")
```

However, to attach feedback, you need the `call` object, which is obtained by using the `.call()` method:

```python
call = predict.call(input_data="your data here")
```

This call object is needed for attaching feedback to the specific response.
After making the call, you can access the output of the operation using:

```python
output = call.output
```

## Attaching Feedback

Feedback is attached directly to the call object. For instance, if you want to add a positive reaction (e.g., 👍) to indicate that the LLM response has passed a vibe check, you can do so by:

```python
call.feedback.add_reaction("👍") # vibe check: passed
```

## Set up Streamlit Application

Here we're going to set up a minimal Streamlit app to serve to our end users:

```python
import weave
from openai import OpenAI
import streamlit as st
from uuid import uuid4

st.title("Add feedback")

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
    return response

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

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
            with weave.attributes({'session': 12345}):
                call = chat_response.call(prompt)
                st.button(":thumbsup:",   on_click=lambda: call.feedback.add_reaction("👍"), key='up')
                st.button(":thumbsdown:", on_click=lambda: call.feedback.add_reaction("👎"), key='down')
                st.session_state.messages.append({"role": "assistant", "content": call.output})
        
def init_weave():
    client = weave.init('feedback-example')

def init_chat_history():
    if "messages" not in st.session_state:
        st.session_state.messages = st.session_state.messages = []

def main():
    session_id = str(uuid4())
    st.session_state['session_id'] = session_id
    init_weave()
    init_chat_history()
    display_chat_messages()
    get_and_process_prompt()

if __name__ == "__main__":
    main()
```

Save this to a file called `feedback.py`. We can run it with `streamlit run feedback.py`. 
Now, you can interact with this application and click the feedback buttons after each response. 
Visit the Weave UI to see the attached feedback.

## Building Automatic Evaluations using Feedback

### Retrieving calls

```python
import weave
client = weave.init('feedback-example')
thumbs_down = client.feedback(reaction="👎")
calls = thumbs_down.refs().calls()
```

### Setting up Evaluation

```python
dataset_examples = [call.inputs['prompt'] for call in calls] # prompt is the input argument to our chat_response call
dataset = weave.Dataset(name='good_examples', rows=dataset_examples)


```