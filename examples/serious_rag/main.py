import os
os.environ['PYTHONASYNCIODEBUG'] = '1'
os.environ['LITELLM_LOG']= 'DEBUG'

import weave
import asyncio

import os, yaml
from dotenv import load_dotenv

from weave_utils import (
    download_source_docs, 
    gen_data,
    WeavePromptTemplate,
    WeaveEmbeddingModel,
    WeaveVectorStore,
    WeaveChatModel,
    WeaveRagModel
)

from evaluate import (
    eval_retrieval,
    HallucinationLLMJudge,
    CorrectnessLLMJudge
)

def main(config):
    # init weave experiment
    weave.init(config["entity"] + "/" + config["project_name"])

    if config["setup"]:
        # data extraction, object: source table
        download_source_docs(**config)
        
        # dataset generation, object: generated dataset
        gen_data(**config)

    if config["benchmark"]:
        # create RAG Model #
        # TODO: publish doesn't work because indx is not saved (model post doesn't work / save)
        # TODO: is weave.publish(vdb) even necessary?
        # TODO: it feels a bit weird to have the publish only for datasets and not for models and other objects
        chat_model = WeaveChatModel(
            name = "ChatModelRag",
            chat_model = config["chat_model"],
            cm_max_new_tokens = config["cm_max_new_tokens"],
            cm_quantize = config["cm_quantize"],
            cm_temperature = config["cm_temperature"],
            inference_batch_size = config["inference_batch_size"],
            device = config["device"],
        )
        embedding_model = WeaveEmbeddingModel(
            embedding_model = config["embedding_model"],
            device = config["device"],
            embedding_model_norm_embed = config["embedding_model_norm_embed"],
        )
        vdb = WeaveVectorStore(
            name = "ClimateVectorStore",
            docs = weave.ref(config["raw_data_artifact"]).get(),
            key = "page_content",
            embedding_model = embedding_model,
            limit = 100,
            chunk_size = config["chunk_size"],
            chunk_overlap = config["chunk_overlap"],
        )
        wf_rag_model = WeaveRagModel(
            chat_model = chat_model,
            vector_store = vdb,
            raw_data_artifact = config["raw_data_artifact"],
            rag_prompt_system = config["rag_prompt_system"],
            rag_prompt_user = config["rag_prompt_user"],
            retrieval_chain_type = config["retrieval_chain_type"],
            inference_batch_size = config["inference_batch_size"],
        )

        # create scoring functions #
        # TODO: when specifying a different name attr but with same model class will we see in Weave?
        # TODO: think about offloading the prompt creation to the judges themselves
        # TODO: check how to split into system and user prompt (related to the above point)
        eval_model = WeaveChatModel(
            name="ChatModelEval",
            chat_model=config["eval_model"],
            cm_max_new_tokens=config["em_max_new_tokens"],
            cm_quantize=config["em_quantize"],
            cm_temperature = config["em_temperature"],
            inference_batch_size = config["inference_batch_size"],
            device = config["device"],
        )
        correctness_prompt = WeavePromptTemplate(
            system_prompt=config["eval_system_prompt"],
            human_prompt=config["eval_corr_prompt_user"],
        )
        hallucination_prompt = WeavePromptTemplate(
            system_prompt=config["eval_system_prompt"],
            human_prompt=config["eval_hall_prompt_user"],
        )

        # run evaluation #
        evaluation = weave.Evaluation(
            dataset = weave.ref(config["dataset_artifact"]).get(),
            scorers = [
                CorrectnessLLMJudge(
                   model=eval_model,
                   prompt=correctness_prompt,
                ),
                HallucinationLLMJudge(
                    model=eval_model,
                    prompt=hallucination_prompt,
                ),
                eval_retrieval,
            ],
        )
        # NOTE: this has to be async in any case (even if scorer and model.predict are not async)
        asyncio.run(evaluation.evaluate(wf_rag_model), debug=True)

if __name__ == "__main__":
    config = {}
    file_path = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(file_path, 'configs/general_config.yaml'), 'r') as file:
        config.update(yaml.safe_load(file))

    if not load_dotenv(os.path.join(file_path, "configs/benchmark.env")):
        print("Environment variables couldn't be found.")

    main(config)
