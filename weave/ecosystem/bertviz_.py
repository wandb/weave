import typing
import bertviz

import weave

from . import huggingface


@weave.op()
def head_view(attention: huggingface.ModelOutputAttention) -> weave.ops.Html:
    model_output = attention.model_output
    model_input = model_output.model_input
    model = model_output.model
    tokens = model.tokenizer().convert_ids_to_tokens(model_input[0])
    html = bertviz.head_view(attention.attention, tokens, html_action="return")
    return weave.ops.Html(html.data)


@weave.op(
    input_type={
        "attention": weave.types.Function({}, huggingface.ModelOutputAttentionType())
    }
)
def head_view_panel(attention) -> weave.panels.Html:
    html = head_view(attention)
    return weave.panels.Html(input_node=weave.ops.html_file(html))
