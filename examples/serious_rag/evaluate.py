import weave
from weave import WeaveList
from weave.flow.scorer import Scorer
from typing import Any, Optional, Union

import numpy as np

from weave_utils import (
    WeaveChatModel,
    WeavePromptTemplate
)

# TODO: find a way to structure cost and latency (maybe other infos) in eval overview through different scorers and different dicts for now (as discussed with Scott)
# TODO: the prompt argument can actually be backed in statically to the respective class (prompts as public vars at doc top)
# TODO: check out instructor and binary grade implementation from LC implementation
# TODO: feedback for ThirdPartyMetricsScorer base clase from Anish
# - I don't understand the core benefit of having that base class?
# - checking if packages are installed and defining the module string seems to be complicated
# - for a potential llm_judge base class as args (check my past tries, Anish's try and think of beneift for presets marketplace? like this example marketplace)
#    - chat_model      - the model that should be used for the evaluation (WeaveChatModel)
#    - prompt_template - prompt template used by chat model (WeavePromptTemplate)
#    - input parsing   - to be able to aggregate or join as is needed for hallucination
#    - output parsing  - to be able to store the text output from chat model into bool or float
    
#######################
# Performance Metrics #
####################### 
## correctness scorer ##
class CorrectnessLLMJudge(Scorer):
    prompt: WeavePromptTemplate
    model: WeaveChatModel

    @weave.op()
    async def score(self, model_output: Optional[dict], query: str, answer: str) -> Any:
        """Score the correctness of the predictions by comparing the query, target answer and pred answer.
           Args:
            - model_output: the dict that will be provided by the model that is evaluated
            - query: the question asked - as defined in the dataset
            - answer: the target answer - as defined in the dataset"""

        # prompt formatting
        human_prompt_args = {
            "query": query,
            "answer": answer,
            "result": model_output["result"],
            }
        messages = self.prompt.format_prompt(
            human_prompt_args=human_prompt_args
        )

        # chat model inference 
        grade = await self.model.predict(messages)
        evaluation = "incorrect" not in grade["content"].strip().lower()
        return {"answer correct": evaluation}
    
    @weave.op()
    def summarize(self, score_rows: WeaveList) -> Optional[dict]:
        """Aggregate all the scores that are calculated for each row by the scoring function.
           Args:
            - score_rows: a WeaveList object, nested dict of metrics and scores
           Returns:
            - nested dict with the same structure as the input"""
        
        # if nothing is provided the weave.flow.scorer.auto_summarize function is used
        # return auto_summarize(score_rows)

        valid_data = [x.get("answer correct") for x in score_rows if x.get("answer correct") is not None]
        count_true = list(valid_data).count(True)
        int_data = [int(x) for x in valid_data]
        
        sample_mean = np.mean(int_data) if int_data else 0
        sample_variance = np.var(int_data) if int_data else 0
        sample_error = np.sqrt(sample_variance / len(int_data)) if int_data else 0

        return {
            "answer correct":{
                "true_count": count_true,
                "true_fraction": sample_mean,
                "stderr": sample_error,
            }
        }

## retrieval scorer ##
@weave.op()
def eval_retrieval(model_output: Optional[dict], main_source: str) -> dict:
    """Evaluate the retrieval accuracy of the predictions: check whether top source document returned by the
       RetrievalQA chain equals the original source document.
       Args:
           - model_output: the dict that will be provided by the model that is evaluated
           - main_source: the target source - as defined in the dataset"""
    
    # post-process prediction results from RetrievalQA in the weave setup.RagNodel
    nr1_retrieval = model_output["source_documents"][0]["url"]
    return {"first retrieval correct": nr1_retrieval == main_source}


##################
# Safety Metrics #
##################
# TODO: check out different safety measure in Anish's RAG

## hallucination scorer
class HallucinationLLMJudge(Scorer):
    prompt: WeavePromptTemplate
    model: WeaveChatModel

    @weave.op()
    async def score(self, model_output: Optional[dict], query: str) -> Any:
        """Score the hallucination of the predictions by comparing the chat context , query and result.
           We use "stuff" context aggregation for the chat context.
           Args:
            - model_output: the dict that will be provided by the model that is evaluated
            - query: the question asked - as defined in the dataset"""

        # TODO: this is the same code as for the RAGModel -> create stuff aggregation as class function to be called here
        # stuff aggregation
        context_documents = [x["page_content"] for x in model_output["source_documents"]]
        chat_context = "\n\n".join(
            [f"Context {i+1}:\n{doc}" for i,
                doc in enumerate(context_documents)]
        )

        # prompt formatting
        human_prompt_args = {
            "chat_context": chat_context,
            "query": query,
            "result": model_output["result"],
        }
        messages = self.prompt.format_prompt(
            human_prompt_args=human_prompt_args
        )

        # evaluation of single example
        grade = await self.model.predict(messages)
        evaluation = "yes" in grade["content"].strip().lower()
        return {"follows from source": evaluation}

######################
# Governance Metrics #
######################
# TODO: add different metrics here (cost, latency, utilizaiton, etc) - check langfuse here