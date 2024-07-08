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
def assemble_feedback_data(calls) -> pd.DataFrame:
    data = []
    # TODO: this doesn't work
    client = client_context.weave_client.get_weave_client()
    thumbs_down = client.feedback(reaction="👎")
    calls = thumbs_down.refs().calls()
    for call in calls:
        # TODO: would be nice to have these as utility functions
        last_reaction, last_comment = None, None
        for i in range(len(call.feedback), 0, -1):
            if call.feedback[i].feedback_type == "wandb.reaction.1":
                last_reaction = call.feedback[i].payload.emoji
            elif call.feedback[i].feedback_type == "wandb.note.1":
                last_comment = call.feedback[i].payload.note
            if last_reaction and last_comment:
                break

        data.append({
            "query": call.inputs['model_output']['query'],
            "prediction": call.inputs['model_output']['result'],
            "used_main_source": call.inputs['model_output']['source_documents'][0]['url'],
            "feedback_reaction": last_reaction,
            "feedback_comment": last_comment,
            "first_retrieval_correct": call.output['correct'].val,
        })
    return pd.DataFrame(data)

if __name__ == "__main__":
    # init page and get project and dataset names
    streamlit_setup()

    # select weave project
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
    edit_mode = st.checkbox("Go to edit mode - once either dataset or operation is selected (is cached)")

    if edit_mode:
        # download data from weave and display in streamlit
        client = start_weave(entity, project_name)

        if data_selector == "Weave Dataset (existing)":
            new_dataset_name = dataset_name.split(":")[0]
            weave_dataset_df = get_weave_dataset(dataset_name)
        elif data_selector == "Weave Operation (production data)":
            new_dataset_name = "annotated_prod_data"
            weave_dataset_df = assemble_production_data(op_name)
        elif data_selector == "Weave Feedback (production data)":
            new_dataset_name = "annotated_feedback_data"
            # TODO: retrieve client and then offload in other function
            #weave_dataset_df = assemble_feedback_data()

            data = []
            thumbs_down = client.feedback(reaction=feedback_name)
            calls = thumbs_down.refs().calls()[-2:]
            for call in calls:
                # TODO: would be nice to have these as utility functions
                last_reaction, last_comment = None, None
                for f in call.feedback[::-1]:
                    if f.feedback_type == "wandb.reaction.1":
                        last_reaction = f.payload["emoji"]
                    elif f.feedback_type == "wandb.note.1":
                        last_comment = f.payload["note"]
                    if last_reaction and last_comment:
                        break

                result_url = call.output["model_output"]["result"]
                first_source_url = call.output["model_output"]["source_documents"][0]

                data.append({
                    "query": call.inputs['example']['query'],
                    # TODO: this also doesn't work within the UI - check why?
                    # "prediction": weave.ref(result_url).get(),
                    # "used_main_source": weave.ref(first_source_url).get(),
                    "feedback_reaction": last_reaction,
                    "feedback_comment": last_comment,
                    "correct": call.output["scores"]["Performance Metrics"]["correct"].val,
                    "first_retrieval": call.output["scores"]["Performance Metrics"]["first_retrieval"].val,
                    "no_hallucination": call.output["scores"]["Safety Metrics"]["no_hallucination"].val,
                })
            weave_dataset_df = pd.DataFrame(data)
        else:
            st.error("Please select a valid data source!")

        # annotate and publish when ready
        edited_df = st.data_editor(weave_dataset_df, num_rows="dynamic")

        # TODO: saving doesn't work yet!
        if st.button("Save Dataset"):
            dataset = weave.Dataset(
                name=new_dataset_name, 
                rows=edited_df.to_dict(orient="records")
            )
            weave.publish(dataset)
            st.success("Successfully saved data to Weave!", icon="✅")