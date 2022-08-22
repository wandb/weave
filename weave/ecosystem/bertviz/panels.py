import bertviz

import weave

from .. import huggingface


@weave.op()
def head_view(attention: huggingface.ModelOutputAttention) -> weave.ops.Html:
    # All the information we need is attached to the ModelOutputAttention object.
    # This is important. In Weave, types should "stand alone", meaning they should
    # contain references to any information that is necessary for their use.

    # we can walk to model_output from attention
    model_output = attention.model_output

    # we can walk to model_input from model_output
    encoded_model_input = model_output._encoded_model_input

    # we can walk to the model
    model = model_output._model

    tokens = model.tokenizer().convert_ids_to_tokens(encoded_model_input[0])

    # Finally call bertviz, which gives us back html.
    html = bertviz.head_view(attention._attention, tokens, html_action="return")

    # The .data attribute contains the html string. Wrap it in the weave Html type.

    # TODO: this would read better as weave.types.Html I think.
    return weave.ops.Html(html.data)


# An op that returns a panel is treated by the WeaveUI code as a panel. It will
# show up in the panel choices if the current expression's output type matches
# the type of the panel input (the first argument in the op declaration.)
@weave.op()
def head_view_panel_render(
    attention: weave.Node[huggingface.ModelOutputAttention],
) -> weave.panels.Html:
    # This is a lazy call! It doesn't execute anything
    html = head_view(attention)

    # We add the lazy call as input to the returned Html panel. Nothing has been
    # computed so far. The UI's Html panel will perform a useNodeValue operation on its
    # input node. Only then will the head_view function finally be called.
    return weave.panels.Html(html)


@weave.op()
def model_view(attention: huggingface.ModelOutputAttention) -> weave.ops.Html:
    # Parallels head_view() to visualize the full matrix of attention heads as rows
    # and layers as columns for each attention map

    # walk to model from attention
    model_output = attention.model_output
    encoded_model_input = model_output._encoded_model_input
    model = model_output._model

    tokens = model.tokenizer().convert_ids_to_tokens(encoded_model_input[0])
    html = bertviz.model_view(attention._attention, tokens, html_action="return")

    # TODO: this would read better as weave.types.Html I think.
    return weave.ops.Html(html.data)


@weave.op()
def model_view_panel_render(
    attention: weave.Node[huggingface.ModelOutputAttention],
) -> weave.panels.Html:
    html = model_view(attention)
    return weave.panels.Html(html)
