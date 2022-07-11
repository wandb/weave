from . import gpt3

from ... import weave_types as types


def test_gpt3model_inferred_type():
    assert gpt3.Gpt3Model.complete.input_type.arg_types == {
        "self": gpt3.Gpt3ModelType(),
        "prompt": types.String(),
        "seed": types.Int(),
    }
    assert gpt3.Gpt3Model.complete.output_type == types.TypedDict(
        {
            "id": types.String(),
            "object": types.String(),
            "created": types.Int(),
            "model": types.String(),
            "choices": types.List(
                types.TypedDict(
                    {
                        "text": types.String(),
                        "index": types.Int(),
                        "logprobs": types.none_type,
                        "finish_reason": types.String(),
                    }
                )
            ),
        }
    )
