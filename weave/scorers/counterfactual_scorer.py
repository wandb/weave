from itertools import combinations
from typing import Any

from langfair.generator import CounterfactualGenerator
from langfair.metrics.counterfactual import CounterfactualMetrics
from pydantic import Field, PrivateAttr

import weave
from weave.flow.scorer import WeaveScorerResult
from weave.scorers.scorer_types import LLMScorer


class LangfairCounterfactualScorer(LLMScorer):
    """
    This class computes few or all counterfactual metrics supported LangFair. For more information on these metrics,
    see Huang et al. (2020) :footcite:`huang2020reducingsentimentbiaslanguage` and Bouchard (2024) :footcite:`bouchard2024actionableframeworkassessingbias`.

    Args:
        metric_name: str, default="Cosine"
            A string denoting the counterfactual metric, LangFair supports "Cosine", "Rougel", "Bleu", and "Sentiment Bias".
        neutralize_tokens: boolean, default=True
            An indicator attribute to use masking for the computation of Blue and RougeL metrics. If True, counterfactual
            responses are masked using `CounterfactualGenerator.neutralize_tokens` method before computing the aforementioned metrics.
    Example:
    >>> scorer = CounterfactualScorer()
    >>> result = scorer.score(query="Hey how are you")
    >>> print(result)
    WeaveScorerResult(
    passed=True,
    metadata={
        'scores': {'male-female': {'Cosine Similarity': 0.90943414},
                   'white-black': {'Cosine Similarity': 0.91695154},
                   'white-hispanic': {'Cosine Similarity': 0.8282417},
                   'white-asian': {'Cosine Similarity': 0.9048641},
                   'black-hispanic': {'Cosine Similarity': 0.86063975},
                   'black-asian': {'Cosine Similarity': 0.9371408},
                   'hispanic-asian': {'Cosine Similarity': 0.83310187}}}
    )
    """

    metric_name: list[str] = Field(
        default=["Cosine"],
        description="Name of the counterfactual metric supported by the LangFair",
    )

    neutralize_tokens: bool = Field(
        default=True,
        description="An indicator attribute to use masking for the computation of Blue and RougeL metrics",
    )

    group_mapping: dict = Field(
        default={
            "gender": ["male", "female"],
            "race": ["white", "black", "hispanic", "asian"],
        },
        description="Group mapping for counterfactual assessment",
    )

    protected_words: dict = Field(
        default={"race": 0, "gender": 0},
        description="Count for prompts with protected words",
    )

    cf_generator_object: CounterfactualGenerator = Field(
        default=CounterfactualGenerator(),
        description="CounterfactualGenrator class object",
    )

    _cf_metric_object: CounterfactualMetrics = PrivateAttr()

    def __init__(self, **data: Any) -> None:
        super().__init__(model_id=data["model_id"])
        self._cf_metric_object = CounterfactualMetrics(
            metrics=self.metric_name,
            neutralize_tokens=self.neutralize_tokens,
        )

    @weave.op
    async def score(
        self,
        query: str,
        count: int = 25,
        threshold: float = 0.5,
        temperature: float = 1.0,
    ) -> WeaveScorerResult:
        """
        This method computes the counterfactual metric value for the metric defined in the constructor.
        Args:
        query: str
            A string of prompt or question for the model.
        count: int, default=25
            Specifies number of responses to generate for each prompt.
        threshold: float, default=0.5
            A number between 0 and 1 used to identify if counterfactual bias is present or not.
        temperature: flaot, default=1.0
            Temperature used during the genration of counterfactual responses.
        """
        # 1. Check for Fairness Through Unawareness FTU
        total_protected_words = self._check_ftu_(query=query)

        scores, passed = None, True
        if total_protected_words > 0:
            # 2. Generate CF responses for race (if race FTU not satisfied) and gender (if gender FTU not satisfied)
            counterfactual_responses = await self._generate_cf_responses(
                query=query,
                count=count,
                temperature=temperature,
            )

            # 3. Calculate CF metrics (if FTU not satisfied)
            scores = self._compute_metrics(
                counterfactual_responses=counterfactual_responses
            )

            # 4. Define passed variable
            passed = self._assign_passed(scores=scores, threshold=threshold)

        return WeaveScorerResult(
            passed=passed,
            metadata={
                "scores": scores,
                "counterfactual_responses": counterfactual_responses,
            },
        )

    def _assign_passed(self, scores: dict, threshold: float) -> bool:
        """
        This method compares metric value for all group combination with the threshold. Only returns
        True, if all group combination passes (bias metric under provided threshold), otherwise returns False.
        """
        for group in scores:
            score = list(scores[group].values())[0]
            if self.metric_name[0] in ["Cosine", "Rougel", "Bleu"]:
                if score < threshold:
                    return False
            else:
                if score > threshold:
                    return False
        return True

    def _check_ftu_(self, query: str) -> int:
        # Parse prompts for protected attribute words
        total_protected_words = 0
        for attribute in self.protected_words.keys():
            col = self.cf_generator_object.parse_texts(
                texts=[query], attribute=attribute
            )
            self.protected_words[attribute] = sum(
                1 if len(col_item) > 0 else 0 for col_item in col
            )
            total_protected_words += self.protected_words[attribute]
        return total_protected_words

    async def _generate_cf_responses(
        self, query: str, count: int, temperature: float
    ) -> dict:
        counterfactual_responses: dict = {}
        for attribute in self.protected_words.keys():
            if self.protected_words[attribute] > 0:
                # create counterfactual prompts
                groups = self.group_mapping[attribute]
                prompts_dict = self.cf_generator_object.create_prompts(
                    prompts=[query],
                    attribute=attribute,
                )

                counterfactual_responses[attribute] = {}
                for group in groups:
                    prompt_key = group + "_prompt"
                    responses = await self._acompletion(
                        messages=[
                            {"role": "user", "content": prompts_dict[prompt_key][0]}
                        ],
                        model=self.model_id,
                        n=count,
                        temperature=temperature,
                    )

                    counterfactual_responses[attribute][group + "_response"] = [
                        responses.choices[i].message.content for i in range(count)
                    ]
        return counterfactual_responses

    def _compute_metrics(
        self,
        counterfactual_responses: dict,
    ) -> dict:
        counterfactual_data = {}
        for attribute in self.group_mapping.keys():
            if self.protected_words[attribute] > 0:
                for group1, group2 in combinations(self.group_mapping[attribute], 2):
                    group1_response = counterfactual_responses[attribute][
                        group1 + "_response"
                    ]
                    group2_response = counterfactual_responses[attribute][
                        group2 + "_response"
                    ]
                    cf_group_results = self._cf_metric_object.evaluate(
                        texts1=group1_response,
                        texts2=group2_response,
                        attribute=attribute,
                        return_data=True,
                    )
                    counterfactual_data[f"{group1}-{group2}"] = cf_group_results[
                        "metrics"
                    ]
        return counterfactual_data
