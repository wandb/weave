import json
import openai
import os
import tempfile
import time

import weave

openai.api_key_path = os.path.expanduser("~/.openai-apikey")


class StoredFileType(weave.types.ObjectType):
    name = "openai-stored-file"
    type_vars = {"purpose": weave.types.String()}  # TODO: enum?

    def __init__(self, purpose=weave.types.String()):
        self.purpose = purpose

    def property_types(self):
        return {
            "bytes": weave.types.Int(),
            "created_at": weave.types.Int(),  # TODO: convert to date
            "filename": weave.types.String(),
            "id": weave.types.String(),
            "object": weave.types.String(),
            "purpose": self.purpose,
            "status": weave.types.String(),  # TODO: enum?
            "status_details": weave.types.none_type,
        }


# TODO: This is a mirror of OpenAI.File, but would we just attach a type
#     to that and not need to make this class at all?


class StoredFile:
    def __init__(
        self, bytes, created_at, filename, id, object, purpose, status, status_details
    ):
        self.bytes = bytes
        self.created_at = created_at
        self.filename = filename
        self.id = id
        self.object = object
        self.purpose = purpose
        self.status = status
        self.status_details = status_details

    # TODO: currently unused
    def get_openai_file(self):
        return openai.File.retrieve(id=self.id)

    @weave.op(
        input_type={
            "self": StoredFileType(weave.types.String()),
        },
        output_type=weave.types.String(),
    )
    def contents(self):
        return openai.File.download(id=self.id).decode()


StoredFileType.instance_classes = StoredFile
StoredFileType.instance_class = StoredFile


class Gpt3DatasetType(StoredFileType):
    name = "gpt3-dataset"
    type_vars = {}

    def __init__(self):
        self.purpose = weave.types.ConstString("fine-tune")


# TODO: we can make a storage manager for OpenAI Files that
#     allows transactional editing of OpenAI files from panels


@weave.weave_class(weave_type=Gpt3DatasetType)
class Gpt3Dataset(StoredFile):
    @weave.op(
        input_type={
            "self": StoredFileType(),
        },
        output_type=weave.types.List(
            weave.types.TypedDict(
                {"prompt": weave.types.String(), "completion": weave.types.String()}
            )
        ),
    )
    def items(self):
        items = []
        for line in openai.File.download(id=self.id).strip().split(b"\n"):
            items.append(json.loads(line))
        return items


Gpt3DatasetType.instance_classes = Gpt3Dataset
Gpt3DatasetType.instance_class = Gpt3Dataset


class Gpt3FineTuneResultsType(StoredFileType):
    name = "gpt3-fine-tune-results-type"
    type_vars = {}

    def __init__(self):
        self.purpose = weave.types.ConstString("fine-tune-results")


# TODO: we can make a storage manager for OpenAI Files that
#     allows transactional editing of OpenAI files from panels


class Gpt3FineTuneResults(StoredFile):
    @weave.op(
        input_type={
            "self": StoredFileType(),
        },
        output_type=weave.ops.ListTableType(
            weave.types.List(
                weave.types.TypedDict(
                    {
                        "step": weave.types.Int(),
                        "elapsed_tokens": weave.types.Float(),
                        "elapsed_examples": weave.types.Float(),
                        "training_loss": weave.types.Float(),
                        "training_sequence_accuracy": weave.types.Float(),
                        "training_token_accuracy": weave.types.Float(),
                    }
                )
            )
        ),
    )
    def table(self):
        contents = openai.File.download(id=self.id)
        with tempfile.NamedTemporaryFile() as f:
            f.write(contents)
            f.seek(0)
            csv = weave.ops.Csv([])
            csv.load(f.name)
        return csv


Gpt3FineTuneResultsType.instance_classes = Gpt3FineTuneResults
Gpt3FineTuneResultsType.instance_class = Gpt3FineTuneResults


@weave.op(
    name="openai-uploadgpt3dataset",
    input_type={
        "items": weave.types.List(
            weave.types.TypedDict(
                {"prompt": weave.types.String(), "completion": weave.types.String()}
            )
        )
    },
    output_type=Gpt3DatasetType(),
    # TODO: we shouldn't need this!
    render_info={"type": "function"},
)
def upload_gpt3_dataset(items):
    with tempfile.TemporaryFile(mode="w+") as f:
        for item in items:
            json.dump(dict(item), f)
            f.write("\n")
        f.seek(0)
        # TODO: purpose can be other stuff, its an enum
        resp = openai.File.create(file=f, purpose="fine-tune")
    return Gpt3Dataset(**resp)


class Gpt3ModelType(weave.types.ObjectType):
    name = "gpt3-model"
    type_vars = {}

    def __init__(self):
        pass

    def property_types(self):
        return {"id": weave.types.String(), "version": weave.types.String()}


@weave.weave_class(weave_type=Gpt3ModelType)
class Gpt3Model:
    def __init__(self, id, version):
        self.id = id
        # self.version is a HACK to force a new object for the demo
        # TDOO
        self.version = version

    @weave.op(
        name="gpt3model-complete",
        input_type={"self": Gpt3ModelType(), "prompt": weave.types.String()},
        output_type=weave.types.TypedDict(
            {
                "id": weave.types.String(),
                "object": weave.types.String(),
                "created": weave.types.Int(),  # TODO: date
                "model": weave.types.String(),  # TODO: date
                "choices": weave.types.List(
                    weave.types.TypedDict(
                        {
                            "text": weave.types.String(),
                            "index": weave.types.Int(),
                            "logprobs": weave.types.none_type,
                            "finish_reason": weave.types.String(),
                        }
                    )
                ),
            }
        ),
    )
    def complete(self, prompt):
        sleep = 1
        for _ in range(5):
            try:
                return openai.Completion.create(model=self.id, prompt=prompt)
            except openai.error.RateLimitError:
                # This error occurs if a model is newly trained or hasn't
                # been queried for awhile, while the OpenAI backend loads
                # it up.
                time.sleep(sleep)
                sleep *= 2
        return openai.Completion.create(model=self.id, prompt=prompt)


Gpt3ModelType.instance_classes = Gpt3Model
Gpt3ModelType.instance_class = Gpt3Model


class Gpt3FineTuneType(weave.types.ObjectType):
    name = "gpt3-fine-tune-type"
    type_vars = {}

    def __init__(self):
        pass

    def property_types(self):
        return {
            "id": weave.types.String(),
            "status": weave.types.String(),
            "fine_tuned_model": weave.types.optional(weave.types.String()),
            # TODO: This is plural in the OpenAI API. Should we make it a list?
            "result_file": weave.types.optional(Gpt3FineTuneResultsType()),
        }


@weave.weave_class(weave_type=Gpt3FineTuneType)
class Gpt3FineTune:
    def __init__(self, id, status, fine_tuned_model, result_file):
        self.id = id
        self.status = status
        self.fine_tuned_model = fine_tuned_model
        self.result_file = result_file

    @weave.mutation
    def update(self):
        fine_tune = openai.FineTune.retrieve(id=self.id)
        # print("FINE_TUNE", fine_tune)
        self.status = fine_tune["status"]
        self.fine_tuned_model = fine_tune["fine_tuned_model"]
        self.result_file = None
        if fine_tune["result_files"]:
            self.result_file = Gpt3FineTuneResults(**fine_tune["result_files"][0])

    @weave.op(
        name="gpt3finetune-model",
        input_type={
            "self": Gpt3FineTuneType(),
        },
        output_type=Gpt3ModelType(),
    )
    def model(self):
        return Gpt3Model(self.fine_tuned_model, self.id)


Gpt3FineTuneType.instance_classes = Gpt3FineTune
Gpt3FineTuneType.instance_class = Gpt3FineTune


@weave.op(
    render_info={"type": "function"},
    name="openai-finetunegpt3",
    input_type={
        "training_dataset": weave.types.List(
            weave.types.TypedDict(
                {"prompt": weave.types.String(), "completion": weave.types.String()}
            )
        ),
        "hyperparameters": weave.types.TypedDict(
            {
                "n_epochs": weave.types.Int(),
                # "learning_rate_multiplier": weave.types.Float(),
            }
        ),
    },
    output_type=weave.types.RunType(
        weave.types.TypedDict({}),
        weave.types.List(weave.types.Any()),
        Gpt3FineTuneType(),
    ),
)
def finetune_gpt3(training_dataset, hyperparameters, _run=None):
    from .. import api

    uploaded = weave.use(upload_gpt3_dataset(training_dataset))
    create_args = {"training_file": uploaded.id}
    for k, v in hyperparameters.items():
        create_args[k] = v
    api.use(_run.print_("Creating fine tune"))
    resp = openai.FineTune.create(**create_args)
    fine_tune = Gpt3FineTune(
        id=resp["id"],
        status=resp["status"],
        fine_tuned_model=resp["fine_tuned_model"],
        result_file=None,
    )
    while True:
        fine_tune.update()
        time.sleep(3)
        api.use(_run.print_("Fine_tune status: %s" % fine_tune.status))
        if fine_tune.status == "succeeded":
            break
    api.use(_run.set_output(fine_tune))


@weave.op(
    render_info={"type": "function"},
    name="openai-finetunegpt3",
    input_type={
        "training_dataset": weave.types.List(
            weave.types.TypedDict(
                {"prompt": weave.types.String(), "completion": weave.types.String()}
            )
        ),
        "hyperparameters": weave.types.TypedDict(
            {
                "n_epochs": weave.types.Int(),
                # "learning_rate_multiplier": weave.types.Float(),
            }
        ),
    },
    output_type=weave.types.RunType(
        weave.types.TypedDict({}),
        weave.types.List(weave.types.Any()),
        Gpt3FineTuneType(),
    ),
)
def finetune_gpt3_demo(training_dataset, hyperparameters, _run=None):
    from .. import api

    print("!!! FINE TUNE DEMO, NOT REALLY FINE-TUNING !!!")
    api.use(_run.print_("Creating fine tune"))
    resp = {
        "id": str(training_dataset._ref) + str(json.dumps(hyperparameters)),
        "status": "running",
        "fine_tuned_model": None,
    }
    fine_tune = Gpt3FineTune(
        id=resp["id"],
        status=resp["status"],
        fine_tuned_model=resp["fine_tuned_model"],
        result_file=None,
    )
    i = 0
    while True:
        api.use(_run.print_("Fine_tune status: running"))
        i += 1
        if i == 6:
            fine_tune.fine_tuned_model = "ada:ft-wandb-2021-10-05-23-25-22"
            fine_tune.status = "succeeded"
            api.use(_run.print_("Fine_tune status: succeeded"))
            break
        time.sleep(3)
    api.use(_run.set_output(fine_tune))
