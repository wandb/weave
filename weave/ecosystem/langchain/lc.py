import dataclasses
import typing
import json
import time

import weave
from weave import artifact_base
from weave.artifact_fs import FilesystemArtifact
from weave.weave_types import Type

from langchain.vectorstores import VectorStore, FAISS
from langchain.vectorstores.base import VectorStoreRetriever
from langchain.chains.combine_documents.base import BaseCombineDocumentsChain
from langchain.chains.combine_documents.stuff import StuffDocumentsChain
from langchain.docstore.document import Document
from langchain.embeddings.base import Embeddings
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.llms import OpenAI
from langchain.chat_models.base import BaseChatModel
from langchain.chat_models import ChatOpenAI
from langchain.chat_models import ChatAnthropic
from langchain.chains import HypotheticalDocumentEmbedder
from langchain.chains.llm import LLMChain
from langchain.llms.base import BaseLLM
from langchain.llms.openai import BaseOpenAI
from langchain.callbacks.tracers.base import BaseTracer
from langchain.chains import RetrievalQA
from langchain.chains.base import Chain
from langchain.chains.retrieval_qa.base import BaseRetrievalQA
from langchain.base_language import BaseLanguageModel
from langchain.schema import BaseRetriever
from langchain.prompts.base import StringPromptTemplate
from langchain.prompts import PromptTemplate, BasePromptTemplate
from langchain.prompts import BaseChatPromptTemplate, ChatPromptTemplate
from langchain.prompts.chat import (
    BaseMessagePromptTemplate,
    BaseStringMessagePromptTemplate,
    ChatMessagePromptTemplate,
    HumanMessagePromptTemplate,
    AIMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain.callbacks.tracers.schemas import Run

from ...ops_domain import trace_tree
from ... import storage
from . import util

import faiss


class WeaveTracer(BaseTracer):
    run: typing.Optional[Run]

    def _persist_run(self, run: "Run") -> None:
        self.run = run


@dataclasses.dataclass(frozen=True)
class DocumentType(weave.types.ObjectType):
    instance_classes = Document

    metadata: weave.types.Type = weave.types.TypedDict()

    def property_types(self) -> dict[str, Type]:
        return {"page_content": weave.types.String(), "metadata": self.metadata}


class VectorStoreType(weave.types.Type):
    instance_classes = VectorStore


# TODO: LangChain uses pydantic, we can infer object types everywhere...
class EmbeddingsType(weave.types.ObjectType):
    instance_classes = Embeddings


class OpenAIEmbeddingsType(EmbeddingsType):
    instance_classes = OpenAIEmbeddings


@dataclasses.dataclass(frozen=True)
class BaseRetrieverType(weave.types.ObjectType):
    instance_classes = BaseRetriever


@dataclasses.dataclass(frozen=True)
class VectorStoreRetrieverType(BaseRetrieverType):
    instance_classes = VectorStoreRetriever

    vectorstore: weave.types.Type = weave.types.Any()

    def property_types(self):
        return {
            "vectorstore": self.vectorstore,
            "search_type": weave.types.String(),
            # TODO: wrong, this is variable.
            "search_kwargs": weave.types.TypedDict(),
        }


@dataclasses.dataclass(frozen=True)
class BasePromptTemplateType(weave.types.ObjectType):
    instance_classes = BasePromptTemplate


@dataclasses.dataclass(frozen=True)
class StringPromptTemplateType(BasePromptTemplateType):
    instance_classes = StringPromptTemplate


@dataclasses.dataclass(frozen=True)
class PromptTemplateType(StringPromptTemplateType):
    instance_classes = PromptTemplate

    def property_types(self) -> dict[str, Type]:
        prop_types = super().property_types()
        prop_types.update(
            {
                "input_variables": weave.types.List(weave.types.String()),
                "template": weave.types.String(),
                "template_format": weave.types.String(),
                "validate_template": weave.types.Boolean(),
            }
        )
        return prop_types


@dataclasses.dataclass(frozen=True)
class BaseChatPromptTemplateType(BasePromptTemplateType):
    instance_classes = BaseChatPromptTemplate


@dataclasses.dataclass(frozen=True)
class ChatPromptTemplateType(BaseChatPromptTemplateType):
    instance_classes = ChatPromptTemplate

    messages: weave.types.Type = weave.types.Any()

    def property_types(self) -> dict[str, Type]:
        prop_types = super().property_types()
        prop_types.update(
            {
                "input_variables": weave.types.List(weave.types.String()),
                "messages": self.messages,
            }
        )
        return prop_types


@dataclasses.dataclass(frozen=True)
class BaseMessagePromptTemplateType(weave.types.ObjectType):
    instance_classes = BaseMessagePromptTemplate


@dataclasses.dataclass(frozen=True)
class BaseStringMessagePromptTemplateType(BaseMessagePromptTemplateType):
    instance_classes = BaseStringMessagePromptTemplate

    prompt: weave.types.Type = weave.types.Any()
    additional_kwargs: weave.types.Type = weave.types.Any()

    def property_types(self):
        return {
            "prompt": self.prompt,
            "additional_kwargs": self.additional_kwargs,
        }


@dataclasses.dataclass(frozen=True)
class ChatMessagePromptTemplateType(BaseStringMessagePromptTemplateType):
    instance_classes = ChatMessagePromptTemplate

    def property_types(self):
        prop_types = super().property_types()
        prop_types.update(
            {
                "role": weave.types.String(),
            }
        )
        return prop_types


@dataclasses.dataclass(frozen=True)
class HumanMessagePromptTemplateType(BaseStringMessagePromptTemplateType):
    instance_classes = HumanMessagePromptTemplate


@dataclasses.dataclass(frozen=True)
class AIMessagePromptTemplateType(BaseStringMessagePromptTemplateType):
    instance_classes = AIMessagePromptTemplate


@dataclasses.dataclass(frozen=True)
class SystemMessagePromptTemplateType(BaseStringMessagePromptTemplateType):
    instance_classes = SystemMessagePromptTemplate


@dataclasses.dataclass(frozen=True)
class ChainType(weave.types.ObjectType):
    instance_classes = Chain


# Hmm... this uses multiple inheritance in langchain, its both ChainType
# and EmbeddingsType. Weave doesn't support that, prefering type dispatch.
@dataclasses.dataclass(frozen=True)
class HyptheticalDocumentEmbedderType(EmbeddingsType):
    instance_classes = HypotheticalDocumentEmbedder

    base_embeddings: weave.types.Type = weave.types.Any()
    llm_chain: weave.types.Type = weave.types.Any()

    def property_types(self):
        return {
            "base_embeddings": self.base_embeddings,
            "llm_chain": self.llm_chain,
        }


@dataclasses.dataclass(frozen=True)
class LLMChainType(ChainType):
    instance_classes = LLMChain

    prompt: weave.types.Type = weave.types.Any()
    llm: weave.types.Type = weave.types.Any()

    def property_types(self):
        return {
            "prompt": self.prompt,
            "llm": self.llm,
            "output_key": weave.types.String(),
        }


@dataclasses.dataclass(frozen=True)
class BaseLanguageModelType(ChainType):
    instance_classes = BaseLanguageModel


@dataclasses.dataclass(frozen=True)
class BaseLLMType(BaseLanguageModelType):
    instance_classes = BaseLLM


@dataclasses.dataclass(frozen=True)
class BaseOpenAIType(BaseLLMType):
    instance_classes = BaseOpenAI

    def property_types(self) -> dict[str, Type]:
        return {
            "model_name": weave.types.String(),
            "temperature": weave.types.Float(),
        }


@dataclasses.dataclass(frozen=True)
class OpenAIType(BaseOpenAIType):
    instance_classes = OpenAI


@dataclasses.dataclass(frozen=True)
class BaseChatModelType(BaseLanguageModelType):
    instance_classes = BaseChatModel


@dataclasses.dataclass(frozen=True)
class ChatOpenAIType(BaseChatModelType):
    instance_classes = ChatOpenAI

    def property_types(self) -> dict[str, Type]:
        return {
            "model_name": weave.types.String(),
            "temperature": weave.types.Float(),
        }


@dataclasses.dataclass(frozen=True)
class ChatAnthropicType(BaseChatModelType):
    instance_classes = ChatAnthropic

    def property_types(self) -> dict[str, Type]:
        return {
            "model": weave.types.String(),
            "temperature": weave.types.Float(),
        }


@dataclasses.dataclass(frozen=True)
class BaseCombineDocumentsChainType(ChainType):
    instance_classes = BaseCombineDocumentsChain

    def property_types(self):
        return {
            "input_key": weave.types.String(),
            "output_key": weave.types.String(),
        }


@dataclasses.dataclass(frozen=True)
class StuffDocumentsChainType(BaseCombineDocumentsChainType):
    instance_classes = StuffDocumentsChain

    llm_chain: weave.types.Type = weave.types.Any()
    document_prompt: weave.types.Type = weave.types.Any()

    def property_types(self):
        prop_types = super().property_types()
        prop_types.update(
            {
                "llm_chain": self.llm_chain,
                "document_prompt": self.document_prompt,
                "document_variable_name": weave.types.String(),
                "document_separator": weave.types.String(),
            }
        )
        return prop_types


@dataclasses.dataclass(frozen=True)
class BaseRetrievalQAType(ChainType):
    instance_classes = BaseRetrievalQA

    combine_documents_chain: weave.types.Type = weave.types.Any()

    def property_types(self):
        return {
            "combine_documents_chain": self.combine_documents_chain,
            "input_key": weave.types.String(),
            "output_key": weave.types.String(),
            "return_source_documents": weave.types.Boolean(),
        }


@dataclasses.dataclass(frozen=True)
class RetrievalQAType(BaseRetrievalQAType):
    instance_classes = RetrievalQA

    retriever: weave.types.Type = weave.types.Any()

    def property_types(self):
        prop_types = super().property_types()
        prop_types.update(
            {
                "retriever": self.retriever,
            }
        )
        return prop_types


class FAISSType(VectorStoreType):
    instance_classes = FAISS

    def save_instance(
        self, obj: FAISS, artifact, name
    ) -> typing.Union[list[str], artifact_base.ArtifactRef, None]:
        # Langchain is inefficient, it resaves all the documents.
        # But in weave we've probably already saved them, so we'd prefer to just store a ref.
        # TODO: replace with weave implementation
        with artifact.new_dir(name) as dir:
            obj.save_local(dir)
        return None

    def load_instance(
        self,
        artifact: FilesystemArtifact,
        name: str,
        extra: typing.Union[list[str], None] = None,
    ) -> typing.Any:
        # TODO: LangChain requires Embeddings when loading, but it drops the embeddings
        # object!
        return FAISS.load_local(artifact.path(name), OpenAIEmbeddings())


@weave.op()
def faiss_from_documents(
    documents: list[Document],
    embeddings: Embeddings,
) -> FAISS:
    return FAISS.from_documents(documents, embeddings)


class DocumentEmbedding(typing.TypedDict):
    document: Document
    # TODO: np array
    embedding: list[float]
    # I made this a string because there's no way to tell Plot
    # its categorical at the moment.
    cluster: str


@weave.weave_class(weave_type=FAISSType)
class FaissOps:
    @weave.op()
    def document_embeddings(vector_store: FAISS) -> list[DocumentEmbedding]:
        embeddings = vector_store.index.reconstruct_n()
        kmeans = faiss.Kmeans(embeddings.shape[1], 20, niter=20, verbose=False)
        kmeans.train(embeddings)
        cluster_distances, cluster_ids = kmeans.index.search(embeddings, 1)
        cluster_ids = cluster_ids.tolist()
        result: list[DocumentEmbedding] = []
        for i, embedding in enumerate(embeddings):
            result.append(
                {
                    "document": vector_store.docstore.search(
                        vector_store.index_to_docstore_id[i]
                    ),
                    "embedding": embedding.tolist(),
                    "cluster": str(cluster_ids[i][0]),
                }
            )
        return result


@weave.op()
def similarity_search(vector_store: VectorStore, query: str) -> list[Document]:
    return vector_store.similarity_search(query)


@weave.op(render_info={"type": "function"})
def openai_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings()


@weave.op(render_info={"type": "function"})
def openai(model_name: str, temperature: float) -> OpenAI:
    return OpenAI(model_name=model_name, temperature=temperature)


@weave.op(render_info={"type": "function"})
def chat_openai(model_name: str, temperature: float) -> ChatOpenAI:
    return ChatOpenAI(model_name=model_name, temperature=temperature)


@weave.op(render_info={"type": "function"})
def chat_anthropic(model_name: str, temperature: float) -> ChatAnthropic:
    return ChatAnthropic(model=model_name, temperature=temperature)


@weave.op(render_info={"type": "function"})
def llm_chain(llm: BaseLanguageModel, prompt: BasePromptTemplate) -> LLMChain:
    return LLMChain(llm=llm, prompt=prompt)


@weave.op(render_info={"type": "function"})
def hypothetical_document_embedder(
    base_embeddings: Embeddings, llm_chain: LLMChain
) -> HypotheticalDocumentEmbedder:
    return HypotheticalDocumentEmbedder(
        base_embeddings=base_embeddings, llm_chain=llm_chain
    )


@weave.op(render_info={"type": "function"})
def retrieval_qa_from_chain_type(
    language_model: BaseLanguageModel, chain_type: str, retriever: VectorStore
) -> RetrievalQA:
    retriever = retriever.as_retriever()
    return RetrievalQA.from_chain_type(
        llm=language_model,
        chain_type=chain_type,
        retriever=retriever,
    )


@weave.weave_class(weave_type=BaseChatModelType)
class BaseChatModelOps:
    @weave.op()
    def predict(self: BaseChatModel, text: str) -> str:
        if text == None:
            # TODO: weave engine doesn't handle nullability on args that aren't the first
            return None  # type: ignore
        return self.predict(text)


@weave.weave_class(weave_type=BaseLLMType)
class BaseLLMOps:
    @weave.op()
    def predict(self: BaseLLM, text: str) -> str:
        if text == None:
            # TODO: weave engine doesn't handle nullability on args that aren't the first
            return None  # type: ignore
        return self.predict(text)


ChainTypeVar = typing.TypeVar("ChainTypeVar", bound=Chain)


@weave.type()
class ChainRunResult(typing.Generic[ChainTypeVar]):
    chain: ChainTypeVar
    query: str
    result: str
    latency: float
    trace: trace_tree.WBTraceTree


@weave.weave_class(weave_type=ChainType)
class ChainOps:
    @weave.op(
        output_type=lambda input_type: ChainRunResult.WeaveType(  # type: ignore
            chain=input_type["chain"]
        )
    )
    def run(chain: Chain, query: str):
        if query == None:
            # TODO: weave engine doesn't handle nullability on args that aren't the first
            return None  # type: ignore
        tracer = WeaveTracer()
        start_time = time.time()
        result = chain.run(query, callbacks=[tracer])
        latency = time.time() - start_time
        lc_run = tracer.run
        if lc_run is None:
            raise ValueError("LangChain run was not recorded")
        span = util.safely_convert_lc_run_to_wb_span(lc_run)
        if span is None:
            raise ValueError("Could not convert LangChain run to Weave span")

        # Returns the langchain trace as part of the result... not really what we
        # want.
        return ChainRunResult(
            chain=chain,
            query=query,
            result=result,
            latency=latency,
            trace=trace_tree.WBTraceTree(json.dumps(storage.to_python(span)["_val"])),
        )


# @weave.weave_class(weave_type=BaseRetrievalQAType)
# class BaseRetrievalQAOps:
#     @weave.op()
#     def run(chain: BaseRetrievalQA, query: str) -> RunResult:
#         if query == None:
#             # TODO: weave engine doesn't handle nullability on args that aren't the first
#             return None  # type: ignore
#         tracer = WeaveTracer()
#         result = chain.run(query, callbacks=[tracer])
#         lc_run = tracer.run
#         if lc_run is None:
#             raise ValueError("LangChain run was not recorded")
#         span = util.safely_convert_lc_run_to_wb_span(lc_run)
#         if span is None:
#             raise ValueError("Could not convert LangChain run to Weave span")

#         # Returns the langchain trace as part of the result... not really what we
#         # want.
#         return RunResult(
#             result=result,
#             trace=trace_tree.WBTraceTree(json.dumps(storage.to_python(span)["_val"])),
#         )
