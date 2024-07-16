---
sidebar_position: 2
hide_table_of_contents: true
---

# Tutorial: Collecting Feedback

Gathering feedback from end users of your application is a useful way to get signal on how to improve it. 

In this tutorial, we'll show how to collect feedback from users of for a RAG-based Knowledge Chatbot using Weave. 

## Use Case - Collecting Feedback to Improve Evaluation Pipeline
In order to successfully deploy LLM apps that correspond to the users' expectation it's important to have an evaluation pipeline that produces representative metrics for both the specific user group and the specific set of use-cases. The easiest way to do that is to directly gather feedback from the users of the application. 

### Feedback Types
We consider three different types of feedback that are useful to improve the evaluation pipeline:

1. **User Feedback:** The user gives direct feedback on the answer of the chatbot. This can be done by either giving a reaction (e.g. thumbs up or thumbs down) or by writing a note.

    * **Pro**: This gives the clearest signal on the performance of the app since the question and the feedback are directly from the user.
    * **Con**: This also gives the noisiest signal since it's subject to the user's mood, the user's understanding of the question, and the user's understanding of the answer.

2. **Expert Feedback:** An expert annotates the answer of the chatbot. This can be done by either giving a score or by writing a note.

    * **Pro**: This gives a more neutral signal on the performance of the app since it's from an expert.
    * **Con**: This might give a less representative signal since it's not from the user. Also it's more expensive to collect this feedback since it requires experts to annotate the data.
    
3. **Synthetic Feedback:** We generate a synthetic evaluation dataset based on the documents the RAG chatbot is supposed to use as context to answer questions.

    * **Pro**: This is the most cost effective option that can be representative without needing to gather and annotate a lot of production data. It also gives the broadest signal before gathering very large datasets since it's generated from the documents that the app is supposed to use to answer the questions.
    * **Con**: This might give a less nuanced signal since it's generated from the documents and not from the user. Also it's more expensive to collect this feedback since it requires generating the data.

So far we have found that a combination of all three types of feedback is the most effective way to improve the evaluation pipeline. The following tutorial will guide you through a systematic evaluation pipeline that uses all three types of feedback with Weave:

1. **1st Evaluation**: We evaluate our RAG chatbot on a synthetic evaluation dataset based on the documents the RAG chatbot is supposed to use as context to answer questions. 
2. **2nd Evaluation:** We deploy the RAG chatbot to a specific group of users and let them ask some questions and encourage them to give some direct feedback (reaction + notes). We track their reactions as positive and negative rates as live evaluation while it's running in production. 
3. **3rd Evaluation:** We pull all question-answer-pairs with a negative reaction into an annotation UI and let experts annotate the given answer with help of the given feedback from the user. We save back the new annotated samples as a new version of the existing evaluation dataset and run evaluations again.

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