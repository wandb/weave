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
        from openai import OpenAI

        client = OpenAI(
            base_url=self.base_url, api_key=os.environ[self.api_key_env_var]
        )
        import time
        import json
        from io import BytesIO

        train_str = BytesIO()
        valid_str = BytesIO()

        for row in train_dataset.rows:
            train_str.write((json.dumps(row) + "\n").encode())

        for row in valid_dataset.rows:
            valid_str.write((json.dumps(row) + "\n").encode())

        train_str.seek(0)
        valid_str.seek(0)

        training_file_id = client.files.create(file=train_str, purpose="fine-tune").id
        print("Training file ID", training_file_id)

        valid_file_id = client.files.create(file=valid_str, purpose="fine-tune").id
        print("Valid file ID", valid_file_id)

        finetuning_job_id = client.fine_tuning.jobs.create(
            training_file=training_file_id,
            validation_file=valid_file_id,
            hyperparameters=hyperparameters,
            model=self.model_name,
        ).id
        print("Fine-tuning job ID", finetuning_job_id)

        while True:
            # This should be tracked with an async run
            fine_tune_result = client.fine_tuning.jobs.retrieve(
                finetuning_job_id,
            )

            print("RESULT", fine_tune_result)
            if (
                fine_tune_result.finished_at != None
                and fine_tune_result.fine_tuned_model != None
            ):
                break
            time.sleep(5)

        return self.__class__(fine_tune_result.fine_tuned_model)  # type: ignore
