import weave
import pandas as pd
import streamlit as st

# streamlit config
st.set_page_config(
    page_title="Weave Annotation",
    layout="wide",
)

# call weave.init only when entity or project name is changed
# caching doesn't work with global init of weave
# @st.cache_resource
def start_weave(entity: str, project_name: str) -> None:
    weave.init(entity + "/" + project_name)

def streamlit_setup() -> None:
    st.title('Annotation with Weave + Streamlit :bee:')
    st.subheader('A simple example of how you can plug-in custom annotation tools to Weave', divider='rainbow')
    st.markdown('You can either get an existing `weave.Dataset` or fetch production data from a `weave.op`')

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

if __name__ == "__main__":
    # init page and get project and dataset names
    streamlit_setup()

    # select weave project
    entity = st.text_input("Enter Weave Entity", "wandb-smle")
    project_name = st.text_input("Enter Weave Project Name", "weave-rag-lc-demo")

    # select data source
    data_selector = st.radio("Select Data Source", ["Weave Dataset (existing)", "Weave Operation (production data)"])
    dataset_name = st.text_input("Enter Weave Dataset URL or NAME:VERSION", "gen_eval_dataset:latest")
    op_name = st.text_input("Enter Weave URL (for now only eval_retrieval)", "weave:///wandb-smle/weave-rag-lc-demo/op/eval_retrieval:1A7I3KF3J5b96hocY5JtIttYvNXFuskJOFR8oGYSr10")

    # start annotation
    edit_mode = st.checkbox("Go to edit mode - once either dataset or operation is selected (is cached)")

    if edit_mode:
        # download data from weave and display in streamlit
        start_weave(entity, project_name)

        if data_selector == "Weave Dataset (existing)":
            new_dataset_name = dataset_name.split(":")[0]
            weave_dataset_df = get_weave_dataset(dataset_name)
        elif data_selector == "Weave Operation (production data)":
            new_dataset_name = "annotated_prod_data"
            weave_dataset_df = assemble_production_data(op_name)
        else:
            st.error("Please select a valid data source!")

        # annotate and publish when ready
        edited_df = st.data_editor(weave_dataset_df, num_rows="dynamic")

        if st.button("Save Dataset"):
            dataset = weave.Dataset(
                name=new_dataset_name, 
                rows=edited_df.to_dict(orient="records")
            )
            weave.publish(dataset)
            st.success("Successfully saved data to Weave!", icon="✅")