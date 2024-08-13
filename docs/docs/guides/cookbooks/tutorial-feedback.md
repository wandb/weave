---
sidebar_position: 2
hide_table_of_contents: true
---

- Motivation
- Setup
- Core content explanation
- One big commented example code
- Call to action
- Optional: additional code needed to run the example

TODOS: 
- add specific links to example workspace book
- shorten intro and movtivation
- find a way to retrieve call when working with already hosted endpoints (probably most important way for people to use for prod feedb)
- think about how an actual RagModel would be retrieved from Weave (with a huge vectorstore?)
- add link to full code at FULL CODE places
- fix comment adding functionality in bith code examples in cookbook and in test application

# Using Feedback with Weave: User and Expert Feedback to Improve Evaluation
In order to successfully deploy LLM apps that correspond to the users' expectation it's important to have an evaluation pipeline that produces representative metrics for both the specific user group and the specific set of use-cases. In order to guarantee this we need to continously gather feedback from the user (user group) and domain experts (use-case).

In this tutorial we'll demonstrate a workflow that we've seen work well for many users. We'll use a custom chatbot as an example app and we'll use a custom annotation UI to gather feedback from the user and domain experts. To simplify the example we'll use Streamlit for both the chatbot app and the annotation UI.

### The Process
Before describing the end-to-end process it's important to consider the different types of feedback that can be gathered:

* **User Feedback:** The user gives direct feedback on the answer of the chatbot. This can be done by only giving a reaction (e.g. thumbs up or thumbs down) or by also writing a note.

    * **Pro**: This gives the most direct signal on the performance of the app since the question and the feedback are directly from the user from the app context.
    * **Con**: This also gives the noisiest signal since it's subject to the user's mood, the user's understanding of the question, and the user's understanding of the answer. Also it only gives a feedback for the final generation and not for the intermediate steps of the generation process which make it harder to improve specific components of the app (e.g. retrieval or generation of the RAG).

* **Expert Feedback:** An expert annotates the answer of the chatbot. This can be done by either requiring only a score or by also writing a note.

    * **Pro**: This gives a more neutral and clear signal on the performance of the app since it's coming from an expert.
    * **Con**: This might give a less representative signal since it's not from the user actually using the app. Also it's more expensive to collect this feedback since it requires to hire experts/annotators to annotate the data.
    
* **Synthetic Feedback:** Using one or multiple LLM judges to evaluate the answer of the chatbot. This can also be done by only giving a score or by also requiring an explanation.

    * **Pro**: This is more cost-effective than annotators and can be done before deploying the app. Also it can be done for multiple LLMs at the same time which can be used to mitigate judge bias.
    * **Con**: This might give a less representative or hallucinated signal compared to the user or expert feedback.

So far we have found that a combination of all three types of feedback is the most effective way to improve the evaluation pipeline. The following tutorial will guide you through the creation of a systematic evaluation pipeline that uses all three types of feedback with Weave:

1. **1st Evaluation (synthetic):**: We use LLM judges to evaluate our RAG chatbot on a synthetic evaluation dataset based on the documents the RAG chatbot is supposed to use as context to answer questions. 
2. **2nd Evaluation (user):** We deploy the RAG chatbot to a specific group of users and let them ask some questions and encourage them to give some direct feedback (reaction + notes). We track their reactions as positive and negative rates as live evaluation while it's running in production. 
3. **3rd Evaluation (expert):** We pull all question-answer-pairs with a negative reaction into an annotation UI and let experts annotate the given answer with help of the given feedback from the user. We save back the new annotated samples as a new version of the existing evaluation dataset and run the evaluations again.

:::note
Regardless of the type of feedback generating a synthetic evaluation dataset based on the documents the RAG chatbot is supposed to use as context to answer questions is a good manner to generate a first representative evaluation dataset (question-answer-sources-pairs) that can be used to evaluate the RAG chatbot before gathering enough production data.
:::

# Implementation
In this tutorial we'll focus on setting up the user and expert feedback loop so we'll skip the synthetic datset generation step and LLM evaluation step and directly jump to the user and expert feedback steps.

## 0. Setup
To follow along this tutorial you'll need to install the following packages:
```bash
pip install weave openai streamlit
```

## 1. Gathering User Feedback from Production
The code discussed in this chapter can be found in `chatbot.py`.

### 1.1 Tracking Calls in Production
There are many different ways to deploy your LLM model into production. In this tutorial we'll show both how to a) deploy our model directly using the Weave model reference (i.e. `weave:///...`) and b) how to work with specific endpoinsts of Weave models that have already been deployed (i.e. `http://...`). 

For both cases we create a very simple chatbot interface using Streamlit that adds some generic functions and chatbot logic that is independant of Weave. The first thing to do in both cases is to initialize Weave (in a cached Streamlit function ideally):

```python
import weave
client = weave.init('wandb-smle/weave-rag-experiments')
```

Atfer that we use the model weave URL to retrieve the actual model and serve it as part of our application. In this case our RagModel expects a "query" and a "n_documents" parameter that specifies how mow many documemt chunks should be extracted and ingested into the prompt: 

```python
import asyncio
import streamlit as st

# download model from Weave - copy & paste from Weave UI
RagModel = weave.ref("weave:///<your-model-url>").get()

# generate answer based on prompt and custom input parameters
data, call = asyncio.run(RagModel.predict.call(prompt, n_documents=2))   

# output parsing, visualizing in streamlit, and add to message history
response = data['result']['content']
st.markdown(response)
st.session_state.messages.append({"role": "assistant", "content": response})
```

Another option is to work with a given URL endpoint at which the model is already served and listening for requests. A very fast way of doing this is to use the `weave serve <model>` command which will automatically serve the model locally with FastAPI and Uvicorn (see under "Use" tab for every Model in the Weave UI). 

```python
import requests

# a simple POST request to the predict route of our endpoint
data = requests.post(
    "http://<url-to-endpoint>/predict",
    json={
        "query": prompt,
        "n_documents": 2,
    },
).json()

# output parsing, visualizing in streamlit, and add to message history
response = data['result']['result']['content']
st.markdown(response)
st.session_state.messages.append({"role": "assistant", "content": response})

```

After putting these function into our full streamlit code we can run the chatbot with `streamlit run chatbot.py`. Check here for the FULL CODE.

### 1.2 User Feedback Collection through Chatbot UI
Once we hav deployed our newest model and are tracking the live calls in production we can focus on gathering feedback on each of these calls. As mentioned in the introduction our first thought here is to gather feedback directly from the user using our Chatbot app. This can be done very easily with Weave - using the `call` object we already returned in our above tracking functions we can add any type of feedback to any traced function call:

As the basis we consider any prediction function that is decorated with Weave - in this case either the `RagModel.predict` function when getting the Weave model directly or the underlying `predict` function that is called when the already deployed model is called.

```python
# highlight-next-line
@weave.op
def predict(input_data):
    # Your prediction logic here
    return some_output
```

When calling this function as is with `RagModel.predict("What is project Drawdown?")` the generation will be traced and a simple answer text is returned.

```python
output = predict(query="your data here") # user question through the App UI
```

To attach feedback, you need the `call` object which is used to reference the specific trace of the generation process for this last question. One way of obtaining the call is by calling the `.call` object specifically instead of just the `predict` function:

```python
output, call = predict.call(input_data="your data here")
```

For the other case where we don't get and download the specific Weave model but assume a already hosted model we'll have to get the call object of the last generation using another function: 

```python
# when inside a decorated function itself
call = weave.get_current_call() 

# when just sending a POST request to a served Weave model
# TDOO: <discuss with Scott>
```

Once we retrieved the specific call object of the last response we can use it to attach any kind of feedback. In this case we'll limit the feedback to a thumbs-up and thumbs-down and written comments. See the FEEDBACK REF section for more info.

```python
# user reaction and comments through Chatbot UI

# genereate response ad visualize assistant answer
with st.chat_message("assistant"):
    with weave.attributes({'session': st.session_state['session_id']}):
        # our call to either of the above-mentioned tracked functions
        response, call = production_chat_response(model_url, prompt)
                
        # add general text feedback field for users to give text feedback
        st.markdown("Your feedback: ")
        feedback_text = st.text_input("", placeholder="Type your thoughts...")
        st.button(":thumbsup:",   on_click=lambda: call.feedback.add_reaction("👍"), key='up')
        st.button(":thumbsdown:", on_click=lambda: call.feedback.add_reaction("👎"), key='down')
        st.button("Submit Feedback", on_click=lambda: call.feedback.add_note(feedback_text), key='submit')
        
        # save assistant response in general flow of application
        st.session_state.messages.append({"role": "assistant", "content": response})
```

## 2. Gathering Expert Feedback from Annotation UI
The code discussed in this chapter can be found in `annotation.py`. 

### 2.1 Fetch Production Calls based on User Feedback
Now that we track our production calls together with specific user feedback we want to use these insights to improve our model. We could filter through all calls with a bad feedback and inspect them manually one-by-one using the Weave UI. Although, this a good manner for first debugging and getting a grasp of specific generations but it's not a scalable manner of continously evaluating our model perforamnces. Hence, in this chapter we'll show how to fetch all bad performing calls, have them annotated/corrected by experts, to then save them as a new version of golden evaluation dataset based on which we calculate quantitaive performance metrics with LLM judges (see introduction).

In order to get all responses that were badly rated by the user we can specifiy a target "reaction":
```python
import weave

# initialize same project as the production tracing project
client = weave.init('<specific weave project>')

# highlight-next-line
thumbs_down = client.feedback(reaction="👎")
# highlight-next-line
calls = thumbs_down.refs().calls()
```

### 2.2 Expert Feedback through Annotation UI
Now we only need to display these production calls in a annotation UI for experts to annotate them. This can be done with different specialized tools (e.g. Argilla) or in a simple Streamlit app.

In the following we have created a simple Streamlit app that extracts the last emoji and comment attached to the trace and displays it along the user query, the model response, and the used source documents.

```python 
import weave
import pandas as pd
import streamlit as st

@st.cache_resource
def start_weave(entity: str, project_name: str):
    # highlight-next-line
    return weave.init(entity + "/" + project_name)

@st.cache_resource
def assemble_feedback_data(entity:str, project_name: str) -> pd.DataFrame:
    data = []
    client = start_weave(entity, project_name)
    # highlight-next-line
    thumbs_down = client.feedback(reaction=feedback_name)
    # highlight-next-line
    calls = thumbs_down.refs().calls()
    print(calls)
    for call in calls:
        last_reaction, last_comment = None, None
        for f in call.feedback[::-1]:
            if f.feedback_type == "wandb.reaction.1":
                last_reaction = f.payload["emoji"]
            elif f.feedback_type == "wandb.note.1":
                last_comment = f.payload["note"]
            if last_reaction and last_comment:
                break

        # NOTE: this can be easily customized based on the needed feedback structure
        data.append({
            # prediction - used as question and target answer and url in dataset
            "query": call.inputs['example']['query'],
            "prediction": call.output["model_output"]["result"]["content"],
            "used_main_source": call.output["model_output"]["source_documents"][0]["url"],
            # feedback - used to guide the annotation
            "feedback_reaction": last_reaction,
            "feedback_comment": last_comment,
        })
    return pd.DataFrame(data)

# store the calls in a pandas DF
weave_dataset_df = assemble_feedback_data("prod_team", "rag_project")
```

Now we're using Streamlit's power to create a simple annotation UI with a single line of code:
```python
edited_df = st.data_editor(weave_dataset_df, num_rows="dynamic")
```

And finally save the new changes as a new version of the existing evaluation dataset:
```python
dataset_name = st.text_input("Enter Existing Dataset NAME:VERSION", "gen_eval_dataset:latest")
dataset_name = dataset_name.split(":")[0]

# get the exisiting dataset as a list of dictionaries
# highlight-next-line
rows = [dict(elem) for elem in weave.ref(dataset_name).get().rows]

# add the newly annotated production 👎 calls to the existing dataset
for elem in edited_df.to_dict(orient="records"):
    rows.append(
        {
            "query": elem["query"], 
            "answer": elem["prediction"], 
            "main_source": elem["used_main_source"],
        }
    )

# update the dataset with the new rows
if st.button("Update Dataset"):
    # highlight-next-line
    dataset = weave.Dataset(
        # highlight-next-line
        name=dataset_name, 
        # highlight-next-line
        rows=rows,
    # highlight-next-line
    )
    # highlight-next-line
    weave.publish(dataset)
    st.success("Successfully updated data to Weave!", icon="✅")
```

In the following you can a screenshot of the simple annotation UI and of the resulting dataset.

![Annotation UI](./imgs/expert_annotation_ui.png)
![Weave Dataset](./imgs/new_annotated_dataset_weave.png)

## 3. Run new Evaluation with the new Dataset
After gathering new 👎 feedback and annotating it, we can now run our evaluation code again. This time we will use the new version of the evaluation dataset and use the comparison feature to understand how the impact of 👎 calls impacted the model performance. Of course it also makes sense to include positive annotated calls into the dataset to balance evaluation dataset. 

For more information on the evaluation workflow see the [Evaluation](./tutorial-eval.md) tutorial for more details.
