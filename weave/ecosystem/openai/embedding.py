from __future__ import annotations
from typing_extensions import (
    NotRequired,
    TypedDict,
)
import typing
import logging
import os

import tiktoken
import numpy as np
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
import openai

import weave
from ... import ops_arrow

logger = logging.getLogger(__name__)
openai.api_key = os.environ.get("OPENAI_API_KEY")

# OpenAI API functions
retry_openai_decorator = retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=(
        retry_if_exception_type(openai.error.Timeout)
        | retry_if_exception_type(openai.error.APIError)
        | retry_if_exception_type(openai.error.APIConnectionError)
        | retry_if_exception_type(openai.error.RateLimitError)
        | retry_if_exception_type(openai.error.ServiceUnavailableError)
    ),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)


@retry_openai_decorator
def _openai_embed(model, input):
    return openai.Embedding.create(input=input, model=model)


# @retry_openai_decorator
# def openai_chatcompletion(model, messages):
#     return openai.ChatCompletion.create(
#         model="gpt-3.5-turbo",  # The deployment name you chose when you deployed the ChatGPT or GPT-4 model.
#         messages=messages,
#     )


# Helper to efficiently embed a set of documents using the OpenAI embedding API
# This is from langchain

embedding_ctx_length = 8191
OPENAI_EMBEDDING_MODEL = "text-embedding-ada-002"
chunk_size = 1000


# Based on the langchain implementation
def embed_texts(texts: list[str], embedding_model: str) -> list[list[float]]:
    embeddings: list[list[float]] = [[] for _ in range(len(texts))]
    tokens = []
    indices = []
    encoding = tiktoken.model.encoding_for_model(embedding_model)
    for i, text in enumerate(texts):
        if embedding_model.endswith("001"):
            # See: https://github.com/openai/openai-python/issues/418#issuecomment-1525939500
            # replace newlines, which can negatively affect performance.
            text = text.replace("\n", " ")
        token = encoding.encode(
            text,
            disallowed_special="all",
        )
        for j in range(0, len(token), embedding_ctx_length):
            tokens += [token[j : j + embedding_ctx_length]]
            indices += [i]

    batched_embeddings = []
    _chunk_size = chunk_size
    for i in range(0, len(tokens), _chunk_size):
        response = _openai_embed(
            embedding_model,
            input=tokens[i : i + _chunk_size],
        )
        batched_embeddings += [r["embedding"] for r in response["data"]]

    results: list[list[list[float]]] = [[] for _ in range(len(texts))]
    num_tokens_in_batch: list[list[int]] = [[] for _ in range(len(texts))]
    for i in range(len(indices)):
        results[indices[i]].append(batched_embeddings[i])
        num_tokens_in_batch[indices[i]].append(len(tokens[i]))

    for i in range(len(texts)):
        _result = results[i]
        if len(_result) == 0:
            average = _openai_embed(embedding_model, input="",)["data"][
                0
            ]["embedding"]
        else:
            average = np.average(_result, axis=0, weights=num_tokens_in_batch[i])
        embeddings[i] = (average / np.linalg.norm(average)).tolist()

    return embeddings


class OpenAIEmbedOptions(TypedDict):
    model: NotRequired[str]


@weave.op()
def openai_embed(
    texts: list[typing.Optional[str]], options: OpenAIEmbedOptions
) -> ops_arrow.ArrowWeaveList[list[float]]:
    model = typing.cast(str, options.get("model", OPENAI_EMBEDDING_MODEL))
    non_none_texts: list[str] = []
    result_positions: list[typing.Optional[int]] = []
    for i, text in enumerate(texts):
        if text is None or text == None:
            result_positions.append(None)
        else:
            result_positions.append(len(non_none_texts))
            non_none_texts.append(text)
    res = embed_texts(non_none_texts, model)
    final_result: list[typing.Optional[list[float]]] = []
    for pos in result_positions:
        if pos is None:
            final_result.append(None)
        else:
            final_result.append(res[pos])
    return ops_arrow.to_arrow(final_result)
