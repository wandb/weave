---
title: Evaluating with Production Data and Expert Feedback
---


:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/eval_prod_expert_feedback.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/eval_prod_expert_feedback.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::



<img src="http://wandb.me/logo-im-png" width="400" alt="Weights & Biases" />
<!--- @wandbcode{cod-notebook} -->

# Evaluating with Production Data and Expert Feedback

Once we gathered test data from actual users (either in internal test environments or from test groups in production) typically the next step is to create an evaluation dataset in which we can run systematic benchmarks. 

In this tutorial, we'll continue on our RAG Chatbot example and extract questions and answers from our production data that were rated as negative by the user. We'll then expose this data to experts to correct our models answer and feed this data back into a new evaluation dataset. To do collect the production and to evaluate the performance we'll use W&B Weave and for the annotation we'll use Streamlit. 

# 1. Setup
To follow along this tutorial you'll need to install the following packages. We will refer to the following Weave workspace where we created a `RagModel` from scratch based on a `faiss` vectorstore and tracked some interaction with user feedback (see previous cookbooks). 

Check out this [RAG Weave workspace](https://wandb.ai/wandb-smle/weave-cookboook-demo/weave/evaluations), [this codebase](https://github.com/NiWaRe/knowledge-worker-weave) on Github, and this [video explanation on Youtube](https://www.youtube.com/watch?v=EVJ1K3fyb0c) for more details.


```python
!pip install weave openai streamlit asyncio requests
```

# 2. Implementation
In order to create a golden dataset based on which we can systematically benchmark our models we have to: 

1. Collect relevant data from production
2. Annotate data with expert feedback
3. Run benchmarks on the annotated data

## 2.1 Collect relevant data from production
When we deploy our RAG Chatbot either to a control group in production or to a user group chances are high that we collect a lot of conversations between the chatbot and different users. Not all of them are actually relevant and to keep our evaluation as high-signal and efficient as possible we want to only gather the data that is relevant for our evaluation - in this example, only data that was rated as bad by the user.


```python
import weave

# 1. Initialize the Weave client
client = weave.init('wandb-smle/weave-cookboook-demo')

# 2. Query the Weave database for all calls that were rated as bad by the user
calls = client.feedback(reaction="👎").refs().calls()
```

## 2.2 Annotate production data with expert feedback
Now that we have the questions, bad answers, and user comments we can expose this data to our experts and ask them to correct the answer. To do this we'll use Streamlit to create a simple annotation interface. Another popular open-source possibility is to use Argilla.

<img src="https://github.com/NiWaRe/knowledge-worker-weave/blob/master/screenshots/expert_annotation_ui.png?raw=true" width="1000" alt="Streamlmait annotation UI" />


```python
import weave
import pandas as pd
import streamlit as st

@st.cache_resource
def start_weave(entity: str, project_name: str):
    return weave.init(entity + "/" + project_name)

@st.cache_resource
def assemble_feedback_data(entity:str, project_name: str) -> pd.DataFrame:
    data = []
    client = start_weave(entity, project_name)

    # get feedback
    thumbs_down = client.feedback(reaction="👎")
    calls = thumbs_down.refs().calls()


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
    dataset = weave.Dataset(
        name=dataset_name, 
        rows=rows,
    )
    weave.publish(dataset)
    st.success("Successfully updated data to Weave!", icon="✅")
```

## 2.3 Run evaluation with new data
After gathering new 👎 feedback and annotating it, we can now run our evaluation code again. This time we will use the new version of the evaluation dataset and use the comparison feature to understand how the impact of 👎 calls impacted the model performance. Of course it also makes sense to include positive annotated calls into the dataset to balance evaluation dataset. 

We can see that we added three new rows compared to our previous version - see the actual dataset [here](https://wandb.ai/wandb-smle/weave-cookboook-demo/weave/object-versions?filter=%7B%22objectName%22%3A%22gen_eval_dataset%22%7D&peekPath=%2Fwandb-smle%2Fweave-cookboook-demo%2Fobjects%2Fgen_eval_dataset%2Fversions%2F7PrGXU1xmpgMyd15zcMuWRXvO0lqV6tqNhMYm9mnZRw%3F%26).

<img src="https://github.com/NiWaRe/knowledge-worker-weave/blob/master/screenshots/new_annotated_dataset_weave.png?raw=true" width="1000" alt="New annotated prod dataset in Weave" />

Based on this new version of our evaluation dataset we can easily run a new evaluation. This will make the evaluation results more representative for your use-case and user-group in production. 

To make sure that you are aware of what version of the dataset you used to calculate the metrics Weave will also let you know whether you are comparing two models with different metrics or evaluation datasets - see the "Dataset inconsistency detected". For more information on the evaluation workflow see the [Evaluation](./tutorial-eval.md) tutorial for more details.

<img src="https://github.com/NiWaRe/knowledge-worker-weave/blob/master/screenshots/weave_dataset_inconsistency.png?raw=true" width="1000" alt="New annotated prod dataset in Weave" />

## Conclusion

In this cookbook we learned how to effectively collected feedback from users and experts to improve on the evaluation dataset to make it more representative for your use-case and user-group in production. We explain how to use Weave to collect specific data from production, let experts annotate it, and then create a new evaluation dataset to evaluate on.

It is as important to continously iterate on your evaluation pipeline as it is to iterate on your actual LLM model - with Weave is much easier to track calls in production, to add variuos types of feedback, and to systematically improve the evaluation pipeline.

Give it a try today and run the attached code to build your own RAG Chatbot!


