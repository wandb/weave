import weave
from weave import client_context

import pandas as pd
import streamlit as st

# streamlit config
st.set_page_config(
    page_title="Weave Annotation",
    layout="wide",
)

# call weave.init only when entity or project name is changed
# caching doesn't work with global init of weave
@st.cache_resource
def start_weave(entity: str, project_name: str):
    return weave.init(entity + "/" + project_name)

def streamlit_setup() -> None:
    st.title('Annotation with Weave + Streamlit :bee:')
    st.subheader('A simple example of how you can plug-in custom annotation tools to Weave', divider='rainbow')
    st.markdown('You can either get an existing `weave.Dataset` or fetch production data with feedback from a `weave.op`')

@st.cache_resource
def get_weave_dataset(dataset_name: str) -> pd.DataFrame:
    return pd.DataFrame(weave.ref(dataset_name).get().rows)

@st.cache_resource
def assemble_production_data(op_name: str) -> pd.DataFrame:
    data = []
    for i, call in enumerate(weave.ref(op_name).get().calls()):
        if i > 5: # limit time since only for demo purposes
            break
        data.append({
            "query": call.inputs['model_output']['query'],
            "prediction": call.inputs['model_output']['result'],
            "used_main_source": call.inputs['model_output']['source_documents'][0]['url'],
            "true_main_source": call.inputs['main_source'],
            "first_retrieval_correct": call.output['first retrieval correct'].val,
        })
    return pd.DataFrame(data)

@st.cache_resource
def assemble_feedback_data(entity:str, project_name: str) -> pd.DataFrame:
    data = []
    client = start_weave(entity, project_name)
    thumbs_down = client.feedback(reaction=feedback_name)
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
            # judge output - used to guide the annotation
            "correct": call.output["scores"]["Performance Metrics"]["correct"].val,
            "first_retrieval": call.output["scores"]["Performance Metrics"]["first_retrieval"].val,
            "no_hallucination": call.output["scores"]["Safety Metrics"]["no_hallucination"].val,
        })
    return pd.DataFrame(data)

if __name__ == "__main__":
    streamlit_setup()
    entity = st.text_input("Enter Weave Entity", "wandb-smle")
    project_name = st.text_input("Enter Weave Project Name", "weave-rag-experiments")

    # select data source
    # TODO: feedback and op should also work together at the same time
    data_selector = st.radio(
        "Select Data Source", 
        ["Weave Dataset (existing)", "Weave Operation (production data)", "Weave Feedback (production data)"]
    )
    dataset_name = st.text_input("Enter Weave Dataset URL or NAME:VERSION", "gen_eval_dataset:latest")
    op_name = st.text_input("Enter Weave URL (for now only eval_retrieval)", "weave:///wandb-smle/weave-rag-lc-demo/op/eval_retrieval:1A7I3KF3J5b96hocY5JtIttYvNXFuskJOFR8oGYSr10")
    feedback_name = st.text_input("Enter Feedback Reaction", "👎")

    # start annotation
    edit_mode = st.checkbox("Go to edit mode. For feedback - adapt the answer and used source based on the feedback and save it as ground truth to the new eval dataset.")
    if edit_mode:
        if data_selector == "Weave Dataset (existing)":
            client = start_weave(entity, project_name)
            new_dataset_name = dataset_name.split(":")[0]
            weave_dataset_df = get_weave_dataset(dataset_name)
        elif data_selector == "Weave Operation (production data)":
            client = start_weave(entity, project_name)
            new_dataset_name = "annotated_prod_data"
            weave_dataset_df = assemble_production_data(op_name)
        elif data_selector == "Weave Feedback (production data)":
            new_dataset_name = "annotated_feedback_data"
            weave_dataset_df = assemble_feedback_data(entity, project_name)
        else:
            st.error("Please select a valid data source!")

        # main annotation window
        edited_df = st.data_editor(weave_dataset_df, num_rows="dynamic")

        # saving back to Weave
        st.subheader('Feeding data back to Weave')
        st.markdown('You can either create a new `weave.Dataset` or append to an existing dataset.')
        data_selector_2 = st.radio(
            "Select Feedback Mode", 
            ["New Weave Dataset", "Update Weave Dataset"]
        )
        if data_selector_2 == "New Weave Dataset":
            new_dataset_name = st.text_input("Enter New Dataset Name", new_dataset_name)
            if st.button("Save Dataset"):
                dataset = weave.Dataset(
                    name=new_dataset_name, 
                    rows=edited_df.to_dict(orient="records")
                )
                weave.publish(dataset)
                st.success("Successfully saved data to Weave!", icon="✅")
        else:
            dataset_name = st.text_input("Enter Existing Dataset NAME:VERSION", "gen_eval_dataset:latest")
            dataset_name = dataset_name.split(":")[0]
            rows = [dict(elem) for elem in weave.ref(dataset_name).get().rows]

            for elem in edited_df.to_dict(orient="records"):
                rows.append(
                    {
                        "query": elem["query"], 
                        "answer": elem["prediction"], 
                        "main_source": elem["used_main_source"],
                    }
                )
            if st.button("Update Dataset"):
                dataset = weave.Dataset(
                    name=dataset_name, 
                    rows=rows,
                )
                weave.publish(dataset)
                st.success("Successfully updated data to Weave!", icon="✅")
        