import typing
import weave

from .dataset import Dataset


@weave.type()
class ChatModel:
    @weave.op()
    def complete(self, messages: typing.Any) -> typing.Any:
        ...

    @weave.op()
    def finetune(
        self,
        train_dataset: Dataset,
        valid_dataset: Dataset,
        hyperparameters: typing.Any,
    ) -> typing.Any:
        from .openai import OpenaiChatModel
        from .anyscale import AnyscaleChatModel

        if not isinstance(self, (OpenaiChatModel, AnyscaleChatModel)):
            # This is because the following code assumes instance properties
            # that are not defined on the base class. Hack for weaveflow merge
            raise ValueError(
                "finetuning implementation only supported for OpenAI and Anyscale models"
            )

        import os
        import openai
        import time
        import json
        from io import StringIO

        train_str = StringIO()
        valid_str = StringIO()

        for row in train_dataset.rows:
            train_str.write(json.dumps(row) + "\n")

        for row in valid_dataset.rows:
            valid_str.write(json.dumps(row) + "\n")

        train_str.seek(0)
        valid_str.seek(0)

        api_base = self.base_url
        api_key = os.environ[self.api_key_env_var]

        training_file_id = openai.File.create(
            api_base=api_base,
            api_key=api_key,
            file=train_str,
            purpose="fine-tune",
        ).id
        print("Training file ID", training_file_id)

        valid_file_id = openai.File.create(
            api_base=api_base,
            api_key=api_key,
            file=valid_str,
            purpose="fine-tune",
        ).id
        print("Valid file ID", valid_file_id)

        finetuning_job_id = openai.FineTuningJob.create(
            api_base=api_base,
            api_key=api_key,
            training_file=training_file_id,
            validation_file=valid_file_id,
            hyperparameters=hyperparameters,
            model=self.model_name,
        ).id
        print("Fine-tuning job ID", finetuning_job_id)

        while True:
            # This should be tracked with an async run
            fine_tune_result = openai.FineTuningJob.retrieve(
                finetuning_job_id,
                api_base=api_base,
                api_key=api_key,
            )

            print("RESULT", fine_tune_result)
            if (
                fine_tune_result["finished_at"] != None
                and fine_tune_result["fine_tuned_model"] != None
            ):
                break
            time.sleep(5)

        return self.__class__(fine_tune_result["fine_tuned_model"])  # type: ignore
