---
sidebar_position: 4
hide_table_of_contents: true
---

# Tutorial: Collecting User Feedback

Gathering feedback from end users of your application is a useful way to get signal on how to improve it. Weave has flexible APIs to attach feedback to tracked calls. You can attach reactions, notes or JSON payloads. In this tutorial, we'll set up a streamlit app that shows 👍👎 to users after each LLM response. Then, we'll download the data from Weave and create a `Dataset` to use as inputs in `Evaluations`.

## Quickstart 

```python
import weave
client = weave.init("project_name_feedback") 

@weave.op
def my_op(input):
    response = 'Kitten Playtime Indicator'
    return {'response': response, 'call_id': weave.get_current_call().id}
    
output = my_op('What does KPI mean?')
print(output['response']) 
import time; time.sleep(0.1)
client.call(call_id).feedback.add_reaction("👍")

# or 
call = my_op.call('What does KPI mean?')
print(call.output)
call.feedback.add_reaction("👍")
```
    
# Gathering Feedback from End Users in Production

Here we're going to set up a minimal Streamlit app to serve to our end users.

## Installation

`pip install openai streamlit weave`

## Implementation

This simple chat UI will send messages to GPT-4o from OpenAI and show the response to the user. Users can then provide feedback on the response by clicking 👍👎 buttons.

To do so, we will:
- Keep the `client` returned from `weave.init('project_name')`.
- Return the ID from the function that's wrapped with `@weave.op` using `weave.get_current_call().id`.
- Attach feedback using `weave_client.call(call_id).feedback.add_reaction("👍")`.
- Optional: We're using `weave.attributes` to track additional metadata, this may be used to filter in the UI later.

```python
import weave
from openai import OpenAI
import streamlit as st

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
# highlight-next-line
weave_client = weave.init('feedback-example')

st.title("Add feedback")

# highlight-next-line
@weave.op # Track our chat function with weave
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
    # highlight-next-line
    return {'response': response, 'call_id': weave.get_current_call().id} # return the call id


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
            with weave.attributes({'session': st.session_state['session_id']}): # optional: attach session state attribute
                output = chat_response(prompt)

                # use the weave client to retrieve the call and attach feedback
                # highlight-next-line
                st.button(":thumbsup:",   on_click=lambda: weave_client.call(output['call_id']).feedback.add_reaction("👍"), key='up')
                # highlight-next-line
                st.button(":thumbsdown:", on_click=lambda: weave_client.call(output['call_id']).feedback.add_reaction("👎"), key='down')
                st.session_state.messages.append({"role": "assistant", "content": output['response']})

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

Save this to a file called `feedback.py`. Run it with `streamlit run feedback.py`. 

Now, you can interact with this application and click the feedback buttons after each response. 
Visit the Weave UI to see the attached feedback.

## Using Feedback in Evaluations

It's common to want to routinely check good/bad production examples against your latest iteration in Evaluations. Feedback in Weave can be used to curate production examples to evaluate against. You can retrieve feedback via API, and add it to a `weave.Dataset` for use within Evaluations. 

To do this for the above example:

```python
import weave
client = weave.init('feedback-example')
thumbs_down = client.feedback(reaction="👎") # retrieve feedback from the client
calls = thumbs_down.refs().calls() # get the associated calls of each feedback

dataset_examples = [{'prompt': call.inputs['prompt']} for call in calls] # prompt is the input argument to our chat_response call
dataset = weave.Dataset(name='feedback_examples', rows=dataset_examples)
weave.publish(dataset)

# You can now use this dataset within evaluations
# Retrieve dataset
retrieved_dataset = weave.ref('feedback_examples').get()

```

Here, we're grabbing all of the feedback of a specific type and getting the associated calls. We're then iterating over them to map them into the format me need for our evaluation dataset. We then publish the dataset and show how we can retrieve it later for use in evaluations.

For more information on our complete feedback API, see [Feedback](/guides/tracking/feedback).
