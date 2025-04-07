import os
import random
import re
import string
import tempfile
from time import sleep
from time import time as time_fn
from typing import Any, Optional, Union

import requests
from huggingface_hub import HfApi

import weave


class NvidiaNeMoEvaluatorScorer(weave.Scorer):
    """
    A scorer that uses NVIDIA's NeMo Evaluator service to evaluate model outputs.

    This scorer interfaces with NVIDIA's NeMo Evaluator service to run evaluations on model outputs
    using specified metrics and prompts.

    Attributes:
        evaluator_url (str): Base URL for the NeMo Evaluator service
        datastore_url (str): Base URL for the datastore service
        namespace (str): Namespace to use for evaluations
        repo_name (str): Name of the repository to store evaluation data
        target_name (Optional[str]): Name of the evaluation target. Auto-generated if not provided
        configuration_name (Optional[str]): Name of the evaluation configuration. Auto-generated if not provided
        evaluator_token (Optional[str]): Authentication token for the evaluator service
        datastore_token (Optional[str]): Authentication token for the datastore service
        dataset_name (Optional[str]): Name of the dataset to evaluate. Auto-generated if not provided
        hf_api (Optional[HfApi]): HuggingFace API client instance. Auto-generated if not provided
        judge_prompt_template (Optional[list]): Template for prompts sent to judge model. Required if configuration_name is not provided
        judge_metrics (Optional[dict]): Metrics configuration for the evaluation. Required if configuration_name is not provided
        judge_url (Optional[str]): URL endpoint for the judge model. Required if target_name is not provided
        judge_model_id (Optional[str]): ID of the model to use as judge. Required if target_name is not provided
        judge_api_key (Optional[str]): API key for accessing the judge model. Required if target_name is not provided
    """

    evaluator_url: str
    datastore_url: str
    namespace: str
    repo_name: str
    target_name: Optional[str] = None
    configuration_name: Optional[str] = None
    evaluator_token: Optional[str] = None
    datastore_token: Optional[str] = None
    dataset_name: Optional[str] = None
    hf_api: Optional[HfApi] = None
    judge_prompt_template: Optional[list[dict[str, Any]]] = None
    judge_metrics: Optional[dict[str, Any]] = None
    judge_url: Optional[str] = None
    judge_model_id: Optional[str] = None
    judge_api_key: Optional[str] = None
    _this_datapoint_id: Optional[str] = None

    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)
        if self.hf_api is None:
            self.hf_api = HfApi(
                endpoint=f"{self.datastore_url}/v1/hf", token=self.datastore_token
            )
        self._validate_services()
        ## Force weave parallelism to 1 due to datastore not being able to handle simultaneous uploads
        os.environ["WEAVE_PARALLELISM"] = "1"

    def _gen_random_datapoint_id(self) -> str:
        return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

    def publish_configuration(self, configuration: dict) -> dict:
        """Helper function: Publishes an evaluation configuration to the NeMo Evaluator service.

        Args:
            configuration (dict): The evaluation configuration to publish, containing metrics and prompt templates.

        Returns:
            dict: The JSON response from the evaluator service containing the published configuration details.
        """
        res = requests.post(
            f"{self.evaluator_url}/v1/evaluation/configurations",
            headers=self._auth_header("evaluator"),
            json=configuration,
        )
        return res.json()

    def publish_target(self, target: dict) -> dict:
        """Helper function: Publishes an evaluation target to the NeMo Evaluator service.

        Args:
            target (dict): The target configuration containing model endpoint and authentication details.

        Returns:
            dict: The JSON response from the evaluator service containing the published target details.
        """
        res = requests.post(
            f"{self.evaluator_url}/v1/evaluation/targets",
            headers=self._auth_header("evaluator"),
            json=target,
        )
        return res.json()

    def upload_dataset(self, dataset: weave.Dataset) -> tuple[dict[str, Any], str]:
        """Helper function: Uploads a dataset to be used for evaluation.

        Initializes the dataset in the evaluator service and extracts a weave ID from the response.

        Args:
            dataset: The dataset to upload for evaluation.

        Returns:
            tuple[dict[str, Any], str]: A tuple containing (initialization_response, extracted_weave_id).
        """
        answer = self._initialize_datasets(dataset)
        id = None

        # Extract weave ID from the initialization response
        if isinstance(answer, dict):
            answer_str = str(answer)
            match = re.search(r"\b(\S*weave\S*)\b", answer_str)
            if match:
                id = match.group(1)

        return answer, id if id is not None else ""

    @weave.op()
    def _validate_services(self) -> None:
        try:
            ds_resp = requests.get(
                f"{self.datastore_url}/v1/datastore/namespaces",
                timeout=5,
                headers=self._auth_header("datastor"),
            )
            ds_resp.raise_for_status()
            ev_resp = requests.get(
                f"{self.evaluator_url}/v1/evaluation/jobs",
                timeout=5,
                headers=self._auth_header("evaluator"),
            )
            ev_resp.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"Service validation failed: {e}")

    @weave.op()
    def _wait_eval_job(
        self, job_url: str, polling_interval: int = 1000, timeout: int = 6000
    ) -> dict:
        """Helper for waiting an eval job.

        NOTE: compensates for when the status does not change at the end. To be fixed.
        """
        start_time = time_fn()
        auth_header = self._auth_header("evaluator")
        res = requests.get(job_url, headers=auth_header)
        while res.json()["status"] != "completed":
            res = requests.get(job_url, headers=auth_header)
            if res.json()["status"] == "failed":
                raise RuntimeError(
                    f"Failed to start eval job in NeMo Evaluator: {res.json()}"
                )
            if res.json()["status_details"]["progress"] is not None:
                if res.json()["status_details"]["progress"] < 100.0:
                    sleep(polling_interval)

                    res = requests.get(job_url, headers=auth_header)
                    status = res.json()["status"]

                    res_status = requests.get(
                        url=f"{job_url}/status", headers=auth_header
                    )

                    print(
                        f"Job status: {status} after {time_fn() - start_time} seconds. Progress {res_status.json()['progress']} "
                    )

                    if time_fn() - start_time > timeout:
                        raise RuntimeError(f"Took more than {timeout} seconds.")

        return res.json()

    def _auth_header(self, service: str) -> dict:
        if self.datastore_token and service == "datastore":
            return {"Authorization": f"Bearer {self.datastore_token}"}
        if self.datastore_token and service == "evaluator":
            return {"Authorization": f"Bearer {self.evaluator_token}"}
        return {}

    @weave.op()
    def _initialize_datasets(self, wv_dataset: weave.Dataset) -> dict[str, Any]:
        if self.hf_api is None:
            raise RuntimeError("HuggingFace API client is not initialized")

        try:
            self.hf_api.create_repo(
                repo_id=f"{self.namespace}/{self.repo_name}", repo_type="dataset"
            )
        except Exception as e:
            print(f"Repo already exists -- using: {self.namespace}/{self.repo_name}")

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write(wv_dataset.to_pandas().to_csv(index=False))
            temp_file_path = temp_file.name
        if self.dataset_name is not None:
            confirm = self.hf_api.upload_file(
                repo_id=f"{self.namespace}/{self.repo_name}",
                path_or_fileobj=temp_file_path,
                path_in_repo=self.dataset_name,
                repo_type="dataset",
            )
        else:
            self._this_datapoint_id = self._gen_random_datapoint_id()
            confirm = self.hf_api.upload_file(
                repo_id=f"{self.namespace}/{self.repo_name}",
                path_or_fileobj=temp_file_path,
                path_in_repo=f"weave-data-{self._this_datapoint_id}.csv",
                repo_type="dataset",
            )

        os.remove(temp_file_path)
        return confirm

    @weave.op()
    def _write_job(
        self, prompt_template: Optional[list] = None, metrics: Optional[dict] = None
    ) -> tuple[str, dict[str, Any]]:
        if self.configuration_name is None:
            self.configuration_name = (
                f"eval-config-{self.repo_name}-{self._this_datapoint_id}"
            )
            if prompt_template is None or metrics is None:
                raise ValueError(
                    "You must provide either 'judge_prompt_template' or 'configuration_name'."
                )

            configuration = {
                "name": self.configuration_name,
                "namespace": self.namespace,
                "type": "custom",
                "params": {"parallelism": 1},
                "tasks": {
                    "llm-as-a-judge": {
                        "type": "chat-completion",
                        "dataset": {
                            "files_url": f"hf://datasets/{self.namespace}/{self.repo_name}/weave-data-{self._this_datapoint_id}.csv",
                        },
                        "params": {"template": {"messages": prompt_template}},
                        "metrics": metrics,
                    }
                },
            }
            try:
                res = requests.post(
                    f"{self.evaluator_url}/v1/evaluation/configs",
                    headers=self._auth_header("evaluator"),
                    json=configuration,
                )
                res.raise_for_status()
            except Exception as e:
                raise RuntimeError(
                    f"Evaluation configuration failed to be created: {str(e)}"
                )

        if self.target_name is None:
            self.target_name = f"eval-target-{self.repo_name}-{self._this_datapoint_id}"
            if (
                self.judge_url is None
                or self.judge_model_id is None
                or self.judge_api_key is None
            ):
                raise ValueError(
                    "You must provide either 'judge_url, judge_model_id, and judge_api_key' or 'target_name'."
                )
            target = {
                "name": self.target_name,
                "namespace": self.namespace,
                "type": "model",
                "model": {
                    "api_endpoint": {
                        "url": self.judge_url,
                        "model_id": self.judge_model_id,
                        "api_key": self.judge_api_key,
                    }
                },
            }
            try:
                res = requests.post(
                    f"{self.evaluator_url}/v1/evaluation/targets",
                    headers=self._auth_header("evaluator"),
                    json=target,
                )
                res.raise_for_status()
            except Exception as e:
                raise RuntimeError(f"Evaluation target failed to be created: {str(e)}")

        job_json = {
            "namespace": self.namespace,
            "config": f"{self.namespace}/{self.configuration_name}",
            "target": f"{self.namespace}/{self.target_name}",
        }

        res = requests.post(
            f"{self.evaluator_url}/v1/evaluation/jobs",
            headers=self._auth_header("evaluator"),
            json=job_json,
        )
        res.raise_for_status()
        response_json = res.json()
        return response_json["id"], response_json

    @weave.op()
    def score(
        self, output: Optional[str] = None, dataset: Optional[weave.Dataset] = None
    ) -> dict[str, Any]:
        """Score model outputs using NVIDIA's NeMo Evaluator service.

        This method evaluates model outputs using the configured NeMo Evaluator service. It can handle either:
        1. A single output string to evaluate
        2. A weave.Dataset containing multiple outputs to evaluate in batch

        Args:
            output (Optional[str]): A single output string to evaluate. Defaults to None.
            dataset (Optional[weave.Dataset]): A dataset containing outputs to evaluate. Defaults to None.

        Returns:
            dict[str, Any]: Evaluation results from the NeMo Evaluator service containing metrics and scores.

        Raises:
            ValueError: If both output and dataset are provided, or if neither is provided.
            RuntimeError: If the evaluation job fails or times out.

        Note:
            Only one of 'output' or 'dataset' should be provided. If both are provided, a ValueError will be raised.
            The method will automatically create a single-row dataset if given a string output.
        """
        if (dataset is not None) and (output is not None):
            raise ValueError("Only one of 'dataset' or 'output' can be provided.")

        if dataset is None:
            dataset = weave.Dataset(rows=[{"output": output}])

        self._initialize_datasets(dataset)
        job_id, res = self._write_job(
            prompt_template=self.judge_prompt_template, metrics=self.judge_metrics
        )

        res = self._wait_eval_job(
            f"{self.evaluator_url}/v1/evaluation/jobs/{job_id}",
            polling_interval=100,
            timeout=600,
        )

        res = requests.get(
            url=f"{self.evaluator_url}/v1/evaluation/jobs/{job_id}/results",
            headers=self._auth_header("evaluator"),
        )

        return res.json()["tasks"]

    @weave.op()
    def summarize(self, score_rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Summarize a list of score rows into aggregated metrics.

        This method takes a list of score dictionaries and merges them recursively, aggregating numeric values
        and maintaining the structure of nested dictionaries. It calculates means for metrics that have 'sum'
        and 'count' fields.

        Args:
            score_rows (list[dict[str, Any]]): A list of dictionaries containing evaluation scores and metrics to be summarized.
                              Each dictionary can contain nested dictionaries and numeric values.

        Returns:
            dict[str, Any]: A merged dictionary containing aggregated metrics, with means calculated where applicable.

        Note:
            - The method recursively merges dictionaries, summing numeric values at matching paths
            - For metrics with 'sum' and 'count' fields, it calculates and updates the 'mean' field
            - Non-numeric values are preserved from the first occurrence
        """

        def recursive_merge(
            a: Union[dict[str, Any], int, float], b: Union[dict[str, Any], int, float]
        ) -> Union[dict[str, Any], int, float]:
            if isinstance(a, dict) and isinstance(b, dict):
                merged: dict[str, Any] = {}
                for key in set(a) | set(b):
                    if key in a and key in b:
                        merged[key] = recursive_merge(a[key], b[key])
                    else:
                        merged[key] = a.get(key, b.get(key))
                return merged
            elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
                return a + b
            else:
                # If we get here, one of the values is not a dict/number, so we keep the first one
                return a

        def recursive_fix_means(d: Union[dict[str, Any], list[Any]]) -> None:
            if isinstance(d, dict):
                if (
                    "sum" in d
                    and "count" in d
                    and isinstance(d.get("sum"), (int, float))
                    and isinstance(d.get("count"), (int, float))
                ):
                    # Safely update mean
                    d["mean"] = d["sum"] / d["count"] if d["count"] != 0 else 0.0
                for key in d:
                    recursive_fix_means(d[key])
            elif isinstance(d, list):
                for item in d:
                    recursive_fix_means(item)

        if not score_rows:
            return {}

        # Merge all dictionaries
        result: dict[str, Any] = score_rows[0].copy()  # Ensure we start with a dict
        for d in score_rows[1:]:
            merged = recursive_merge(result, d)
            if not isinstance(merged, dict):
                raise TypeError("Unexpected non-dictionary result from recursive_merge")
            result = merged

        # Fix mean values
        recursive_fix_means(result)

        return result
