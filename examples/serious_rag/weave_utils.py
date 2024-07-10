import os, re, random
from tqdm import tqdm
from pathlib import Path
from typing import Any, List, Dict, Optional
from pydantic import PrivateAttr

import weave
import asyncio
from weave.trace import serializer 
from weave.trace.vals import TraceTable
from weave.trace.custom_objs import MemTraceFilesArtifact

import faiss
import numpy as np
import pandas as pd

from litellm import (
    embedding, 
    aembedding, 
    completion,
    acompletion,
)

from langchain_community.document_loaders import WebBaseLoader, OnlinePDFLoader, DataFrameLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Weave Serializers are used to define how non-primitive data types are stored on Weave
# Weave Objects allow custom objects to be displayed other than just their __str__ on Weave

#########
# MODEL #
#########
# TODO: check what dict is outputed from litellm in predict
# TODO: replace Any type for _model with something more sensible
# TODO: validate whether extra handling of gpt is necessary
# TODO: check with developers of litellm (one wrote me) why they re-init the model on every predict
# TODO: implement local models or HF logic (check out logic from lc project and Thomas' PR)
class WeaveChatModel(weave.Model):
    """
    We define an extra ChatModel class to be able store and version more parameters than just the model name.
    Especially, relevant if we consider fine-tuning (locally or aaS) because of specific parameters.
    """
    chat_model: str
    cm_temperature: float
    cm_max_new_tokens: int
    cm_quantize: bool
    inference_batch_size: int
    device: str
    _model: Any = PrivateAttr()

    def model_post_init(self, __context):
        # either use LiteLLM or local models
        pass

    @weave.op()
    async def predict(self, query: List[str]) -> dict:
        completion_args = {
            "model": self.chat_model,
            "messages": query,
            "temperature": self.cm_temperature,
            "max_tokens": self.cm_max_new_tokens,
        }
        if "gpt" not in self.chat_model:
            completion_args["system"] = query.pop(0)["content"]
        response = await acompletion(**completion_args)

        # TODO: make sure that copied values are returned and not references
        return dict(response.choices[0].message)
    
# TODO: check whether this will be recognized as "predict" for weave.Model
# TODO: make sure that return type will be list of list of floats
# TODO: implement the difference of embedding model being a local model, a string to HF or a string to LiteLLM
class WeaveEmbeddingModel(weave.Model):
    """
    We define an extra WeaveEmbeddingModel class to be able store and version more parameters than just the model name.
    Especially, relevant if we consider fine-tuning (locally or aaS) because of specific parameters.
    """
    embedding_model: str
    device: str
    embedding_model_norm_embed: bool
    _model: Any = PrivateAttr()

    def model_post_init(self, __context):
        # either use LiteLLM or local models
        # self._model = HuggingFaceEmbeddings(
        #     model_name=self.embedding_model,
        #     model_kwargs={"device": self.device},
        #     encode_kwargs={"normalize_embeddings": self.embedding_model_norm_embed},
        # )
        pass

    @weave.op()
    def embedd(self, docs: List[str]) -> List[float]:        
        doc_embeddings = embedding(
            model=self.embedding_model,
            input=docs,
            #logger_fn=lambda x:print(f"LITELLM CALL: {x}"),
        )
        if len(docs) == 1:
            return [doc_embeddings["data"][0]["embedding"]]
        else:
            return [doc_embedding["embedding"] for doc_embedding in doc_embeddings["data"]]

    @weave.op()
    async def aembedd(self, docs: List[str]) -> List[float]:        
        doc_embeddings = await aembedding(
            model=self.embedding_model,
            input=docs,
            #logger_fn=lambda x:print(f"LITELLM CALL: {x}"),
        )
        if len(docs) == 1:
            return doc_embeddings["data"][0]["embedding"]
        else:
            return [doc_embedding["embedding"] for doc_embedding in doc_embeddings["data"]]
    
# TODO: check if this necessary and how to make more general next to OpenAI Models
class WeavePromptTemplate(weave.Object):
    system_prompt: str
    human_prompt: str

    @weave.op()
    def format_prompt(
        self,
        system_prompt_args: Optional[Dict[str, str]] = {},
        human_prompt_args: Optional[Dict[str, str]] = {},
    ):
        "A formatting function for OpenAI models"
        system_prompt_formatted = self.system_prompt.format(**system_prompt_args)
        human_prompt_formatted = self.human_prompt.format(**human_prompt_args)
        messages = [
            {"role": "system", "content": system_prompt_formatted},
            {"role": "user", "content": human_prompt_formatted},
        ]
        return messages
    
###############
# VECTORSTORE #
###############

def save_instance(obj: faiss.Index, artifact: MemTraceFilesArtifact, name: str) -> None:
    """
    Allow faiss index stores to be saved in Weave.
    """
    with artifact.writeable_file_path(f"{name}.faissindex") as write_path:
        faiss.writeindex(obj, write_path)

def load_instance(artifact: MemTraceFilesArtifact, name: str) -> faiss.Index:
    """
    Allow faiss index stores to be loaded from Weave.
    """
    return faiss.readindex(artifact.path(f"{name}.faissindex"))

# TODO: check Anish's implementation for more mature class 
# (multi-process embeddings, pre-computing, different distance functions - also how to extend index)
class WeaveVectorStore(weave.Object):
    """
    WeaveVectorStore object that holds index model, docs reference, and embedding model as str.
    It should be used to both init and search the index.
    Modified from hooman chatbot: https://github.com/wandb/hooman/blob/main/faiss_vectorstore.py
    Inspired by Anish's demo: https://github.com/ash0ts/snowflake-arctic-weave-demo
    """
    docs: weave.Dataset
    embedding_model: WeaveEmbeddingModel 
    key: str = "page_content" 
    limit: int = -1
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    _chunked_docs: Optional[List[Dict]] = None
    _index: Optional[faiss.IndexFlat] = None
        
    # TODO: check if better way to store chunked docs (now it would be hard to connect chunks with meta-data), also do parallel
    # TODO: check how the others allow the loading of existing stores
    # TODO: add logic that checks if serializers already exist (and also if this the best place to register the seralizers)
    # TODO: in _chunk_docs weave objects can't simply be copied (also not using async) -- a = weave_obj will automatically be a reference
    @weave.op()
    def model_post_init(self, __context: Any) -> None:
        """
        Create the FAISS index and store the embeddings.
        """
        # add serialization to be able tstore FAISS vectordatabase
        serializer.register_serializer(faiss.Index, save_instance, load_instance)

        # embedd the docs
        if not self._index:
            asyncio.run(self._embed_all_docs())
        else:
            print("An index has already been created. Please call search to search the index.")
    
    @weave.op()
    async def _chunk_docs(self, ref_col: str, non_chunked_docs: TraceTable) -> List[str]:
        """
        Chunk the documents in the dataset. Also convert Weave types into primitive types while doing so.
        """
        if not (self.chunk_size and self.chunk_overlap):
            raise ValueError("No chunk_size or chunk_overlap provided. Please provide both.")
        
        chunked_docs = []
        for doc in non_chunked_docs:
            ref_field_list = doc[ref_col].split()
            for i in range(0, len(ref_field_list), self.chunk_size - self.chunk_overlap):
                new_sub_doc = {k: v for k, v in doc.items()}
                new_sub_doc[ref_col] = " ".join(ref_field_list[i:i + self.chunk_size])
                chunked_docs.append(new_sub_doc)
        return chunked_docs

    @weave.op()
    async def _embed_all_docs(self) -> None:
        """
        Embed all documents in the dataset, chunk them, and create the FAISS index.
        """
        if not self.docs:
            raise ValueError("No documents found in the dataset.")

        # Chunk and embed documents concurrently    
        self._chunked_docs = await self._chunk_docs(ref_col=self.key, non_chunked_docs=self.docs.rows[:self.limit])
        embedding_tasks = [self.embedding_model.aembedd(docs=[doc[self.key]]) for doc in self._chunked_docs]
        embeddings_list = await asyncio.gather(*embedding_tasks)
        
        ## Create FAISS index and add the embeddings
        self._index = faiss.IndexFlatIP(len(embeddings_list[0]))
        embeddings_matrix = np.array(embeddings_list, dtype=np.float32)
        self._index.add(embeddings_matrix)

    @weave.op()
    def search(self, query: str, k: int) -> List[Dict]:
        """
        Search for the appropriate document chunks using faiss.IndexFlat.search returning max k vectors.
        Return a list of dicts with at least the keys "content" and "url" (used in eval).
        """
        if not self._index:
            raise ValueError("No index has been created. Please call create first.")

        embedded_query = self.embedding_model.embedd(docs=[query])
        query_vector = np.array(
            embedded_query, 
            dtype=np.float32
        )
        if query_vector.shape[1] != self._index.d:
            raise ValueError(f"Query vector shape {query_vector.shape} does not match index shape {self._index.d}")
        
        # scores, indices = await asyncio.to_thread(self.index.search, query_vector, k)
        scores, indices = self._index.search(query_vector, k)

        # TODO: wrap in list to make sure that value is returned and not reference
        return list([self._chunked_docs[int(i)] for i in indices[0]])
    
###########
# GENERAL #
###########
# TODO: check Anish's RAG example (pre- and post-processing functions, why @dataclass PromptTemplate)
# TODO: refactor download_source_docs and gen_data to work without langchain
class WeaveRagModel(weave.Model):
    chat_model: WeaveChatModel
    vector_store: WeaveVectorStore
    rag_prompt_user: str
    rag_prompt_system: str
    raw_data_artifact: str
    retrieval_chain_type: str
    inference_batch_size: int
    _prompt: WeavePromptTemplate = PrivateAttr()

    def model_post_init(self, __context):
        self._prompt = WeavePromptTemplate(
            system_prompt=self.rag_prompt_system,
            human_prompt=self.rag_prompt_user,
        )

    @weave.op()
    async def predict(self, query: str, n_documents: int = 2) -> dict:
        # vectorstore search
        context_documents = self.vector_store.search(query=query, k=n_documents)

        # prompt formatting
        context = "\n\n".join(
            [f"Context {i+1}:\n{doc}" for i,
                doc in enumerate(context_documents)]
        )
        human_prompt_args = {
            "question": query,
            "context": context,
        }
        messages = self._prompt.format_prompt(
            human_prompt_args=human_prompt_args
        )

        # chat model inference 
        answer = await self.chat_model.predict(messages)
        return {"result": answer, "source_documents": context_documents}
    
# TODO: replace langchain download and extraction with own functions
@weave.op()
def download_source_docs(
        source_list_path: str,
        raw_data_artifact: str,
        **kwargs,
    ) -> None:
    """Download sources and save them as table artifact to Weave"""

    # Read the sources list
    sources_list_df = pd.read_csv(Path(__file__).parent/source_list_path)
    sources_list = sources_list_df.to_dict(orient="records")

    # Initialize a list to store all downloaded sources
    downloaded_sources = []

    # Define loader mapping for different types of sources
    loader_mapping = {
        "pdf": OnlinePDFLoader,
        "web": WebBaseLoader
    }
    for source in tqdm(sources_list, desc="Downloading sources"):
        # Select the appropriate loader and download the source
        loader_cls = loader_mapping.get(source["type"], WebBaseLoader)
        extracted_raw = loader_cls(source["url"]).load()

        for extracted in extracted_raw:
            extracted_dict = extracted.dict()
            extracted_dict["metadata"] = str(extracted_dict["metadata"])  # Convert metadata to string for Weave compatibility
            extracted_dict.update(source)  # Add the original source info to extracted data
            downloaded_sources.append(extracted_dict)

    # Convert the list of dictionaries to a DataFrame
    sources_df = pd.DataFrame(downloaded_sources, columns=sources_list_df.columns.tolist() + ["page_content", "metadata"])

    # Create and publish the dataset to Weave
    dataset = weave.Dataset(
        name=raw_data_artifact,
        rows=sources_df.to_dict(orient="records")
    ) 
    weave.publish(dataset)

# TODO: replace langchain chunking with own functions
@weave.op()
async def gen_data(
        gen_model: WeaveChatModel,
        prompt_template: WeavePromptTemplate,
        raw_data_artifact: str,
        dataset_artifact: str,
        questions_per_chunk: int,
        max_chunks_considered: int,
        source_chunk_size: int,
        source_chunk_overlap: int,
        **kwargs,
    ) -> None:
    """Generate question-answer-source pairs for the provided sources and upload to Weave.
       Inspired by llama_index.evaluation.DatasetGenerator that generates questions per document.
       We will assume a document to be the entirety of a given source. In contrary to LlamaIndex
       we will not first generate questions and the responses in a separate step but we will generate
       both questions and answers at the same time and use custom parsing to extract the pairs."""
    
    # weave: get sources and split into chunks (with :latest version)
    source_df = pd.DataFrame(weave.ref(raw_data_artifact).get().rows)
    source_docs = DataFrameLoader(source_df, page_content_column="page_content").load()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=source_chunk_size,
        chunk_overlap=source_chunk_overlap
    )
    all_splits = text_splitter.split_documents(source_docs)

    # Sample uniformly from all splits
    sampled_docs = random.sample(all_splits, min(max_chunks_considered, len(all_splits)))

    # Generate questions and answers concurrently per sampled_doc
    queries, answers, sources = [], [], []

    async def generate_qa_pairs(doc):
        """Generate questions and answers for a given document."""
        messages = prompt_template.format_prompt(
            human_prompt_args={
                "questions_per_chunk": questions_per_chunk,
                "source_str": doc.page_content,
            }
        )
        output = await gen_model.predict(messages)

        doc_queries = re.findall(r"QUESTION: (.*)\nANSWER:", output['content'])
        doc_answers = re.findall(r"ANSWER: (.*)", output['content'])
        doc_sources = [doc.metadata['url']] * questions_per_chunk

        return doc_queries, doc_answers, doc_sources

    results = await asyncio.gather(*[generate_qa_pairs(doc) for doc in sampled_docs])

    # Aggregate results
    for doc_queries, doc_answers, doc_sources in results:
        queries.extend(doc_queries)
        answers.extend(doc_answers)
        sources.extend(doc_sources)

    # Create and publish the dataset
    weave.publish(weave.Dataset(
        name=dataset_artifact,
        rows=[{"query": query, "answer": answer, "main_source": source}
              for query, answer, source in zip(queries, answers, sources)]
    ))
