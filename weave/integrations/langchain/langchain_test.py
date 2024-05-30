import os
from typing import Any, Optional

import pytest
from weave.trace_server import trace_server_interface as tsi
from weave.weave_client import WeaveClient


def filter_body(r: Any) -> Any:
    r.body = ""
    return r


def flatten_calls(
    calls: list[tsi.CallSchema], parent_id: Optional[str] = None, depth: int = 0
) -> list:
    def children_of_parent_id(id: Optional[str]) -> list[tsi.CallSchema]:
        return [call for call in calls if call.parent_id == id]

    children = children_of_parent_id(parent_id)
    res = []
    for child in children:
        res.append((child, depth))
        res.extend(flatten_calls(calls, child.id, depth + 1))

    return res


def op_name_from_ref(ref: str) -> str:
    return ref.split("/")[-1].split(":")[0]


def assert_correct_calls_for_chain_invoke(calls: list[tsi.CallSchema]) -> None:
    assert len(calls) == 4

    flattened = flatten_calls(calls)
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
    exp = [
        ("langchain.Chain.RunnableSequence", 0),
        ("langchain.Prompt.PromptTemplate", 1),
        ("langchain.Llm.ChatOpenAI", 1),
        ("openai.chat.completions.create", 2),
    ]
    assert got == exp


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_simple_chain_invoke(client: WeaveClient) -> None:
    from langchain_core.prompts import PromptTemplate
    from langchain_openai import ChatOpenAI

    from .langchain import WeaveTracer

    tracer = WeaveTracer()
    config = {
        "callbacks": [tracer],
    }
    api_key = os.environ.get("OPENAI_API_KEY", "sk-DUMMY_KEY")
    llm = ChatOpenAI(openai_api_key=api_key, temperature=0.0)
    prompt = PromptTemplate.from_template("1 + {number} = ")

    llm_chain = prompt | llm
    output = llm_chain.invoke({"number": 2}, config=config)

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert_correct_calls_for_chain_invoke(res.calls)


def assert_correct_calls_for_chain_batch(calls: list[tsi.CallSchema]) -> None:
    # print(calls)
    flattened = flatten_calls(calls)
    for call in flattened:
        print(call)
        print("-"*80)
    assert len(calls) == 8

    # flattened = flatten_calls(calls)
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
    print(got)
    # exp = [
    #     ("langchain.Chain.RunnableSequence", 0),
    #     ("langchain.Prompt.PromptTemplate", 1),
    #     ("langchain.Llm.ChatOpenAI", 1),
    #     ("openai.chat.completions.create", 2),
    # ]
    # assert got == exp

@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_simple_chain_batch(client: WeaveClient) -> None:
    from langchain_core.prompts import PromptTemplate
    from langchain_openai import ChatOpenAI

    from .langchain import WeaveTracer

    tracer = WeaveTracer()
    config = {
        "callbacks": [tracer],
    }
    api_key = os.environ.get("OPENAI_API_KEY", "sk-DUMMY_KEY")
    llm = ChatOpenAI(openai_api_key=api_key, temperature=0.0)
    prompt = PromptTemplate.from_template("1 + {number} = ")

    llm_chain = prompt | llm
    output = llm_chain.batch([{"number": 2}, {"number": 3}], config=config)

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert_correct_calls_for_chain_batch(res.calls)


def assert_correct_calls_for_rag_chain(calls: list[tsi.CallSchema]) -> None:
    print(len(calls))
    flattened = flatten_calls(calls)
    for call in flattened:
        print(call)
        print("-"*80)


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_simple_rag_chain(client: WeaveClient) -> None:
    from langchain_community.document_loaders import TextLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import Chroma
    from langchain_openai import OpenAIEmbeddings, ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnablePassthrough
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.documents import Document
    from typing import List

    from .langchain import WeaveTracer

    loader = TextLoader("integrations/langchain/test_data/paul_graham_essay.txt")
    docs = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)

    vectorstore = Chroma.from_documents(documents=splits, embedding=OpenAIEmbeddings())
    retriever = vectorstore.as_retriever()

    prompt = ChatPromptTemplate.from_template(
        "You are an assistant for question-answering tasks. " 
        "Use the following pieces of retrieved context to answer the question. "
        "If you don't know the answer, just say that you don't know. "
        "Use three sentences maximum and keep the answer concise.\n"
        "Question: {question}\nContext: {context}\nAnswer:")

    llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0)

    def format_docs(documents: List[Document]) -> List[str]:
        return "\n\n".join(doc.page_content for doc in documents)

    # Chain
    rag_chain = (
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
    )

    rag_chain.invoke({"question": "What is the essay about?"}, config={"callbacks": [WeaveTracer()]})

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert_correct_calls_for_rag_chain(res.calls)



