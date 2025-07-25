import os
from collections.abc import Generator
from unittest.mock import patch

import pytest
import tiktoken

import weave
from weave.integrations.integration_utilities import (
    filter_body,
    flatten_calls,
    op_name_from_ref,
)
from weave.trace.context import call_context
from weave.trace.weave_client import Call, WeaveClient
from weave.trace_server import trace_server_interface as tsi


@pytest.fixture(scope="session", autouse=True)
def ensure_tiktoken_file() -> Generator[None, None, None]:
    enc = tiktoken.get_encoding("cl100k_base")
    enc.encode("Test")
    return


def assert_ends_and_errors(calls: list[tuple[Call, int]]) -> None:
    for call, _depth in calls:
        assert call.ended_at is not None
        assert call.exception is None


def assert_correct_calls_for_chain_invoke(
    calls: list[Call],
    prompt_template_name_part: str = "PromptTemplate",
) -> None:
    flattened = flatten_calls(calls)
    assert len(flattened) == 4
    assert_ends_and_errors(flattened)

    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
    exp = [
        ("langchain.Chain.RunnableSequence", 0),
        ("langchain.Prompt." + prompt_template_name_part, 1),
        ("langchain.Llm.ChatOpenAI", 1),
        ("openai.chat.completions.create", 2),
    ]
    assert got == exp


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_simple_chain_invoke(
    client: WeaveClient,
) -> None:
    from langchain_core.prompts import PromptTemplate
    from langchain_openai import ChatOpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "sk-1234567890abcdef1234567890abcdef")

    llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=api_key, temperature=0.0)
    prompt = PromptTemplate.from_template("1 + {number} = ")
    long_str = (
        "really_massive_name_that_is_longer_than_max_characters_which_would_be_crazy"
    )
    name = long_str + long_str
    prompt.name = name

    exp_name = "really_massive_name_that_is_longer_than_max_characte_ff6e_at_is_longer_than_max_characters_which_would_be_crazy"

    llm_chain = prompt | llm
    _ = llm_chain.invoke({"number": 2})

    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert_correct_calls_for_chain_invoke(calls, exp_name)

    call = calls[0]
    # Assert that the call has usage metadata
    assert call.summary is not None
    assert "usage" in call.summary
    assert "gpt-4o-mini-2024-07-18" in call.summary["usage"].unwrap()


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_simple_chain_invoke_no_client(client) -> None:
    """If no client is available, we should not trace the call, and also not crash."""
    from langchain_core.prompts import PromptTemplate
    from langchain_openai import ChatOpenAI

    client.finish()

    api_key = os.environ.get("OPENAI_API_KEY", "sk-1234567890abcdef1234567890abcdef")

    llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=api_key, temperature=0.0)
    prompt = PromptTemplate.from_template("1 + {number} = ")
    long_str = (
        "really_massive_name_that_is_longer_than_max_characters_which_would_be_crazy"
    )
    name = long_str + long_str
    prompt.name = name

    exp_name = "really_massive_name_that_is_longer_than_max_characte_ff6e_at_is_longer_than_max_characters_which_would_be_crazy"

    llm_chain = prompt | llm
    _ = llm_chain.invoke({"number": 2})


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
@pytest.mark.asyncio
@pytest.mark.skip  # TODO: remove this once the langchain issue is fixed
async def test_simple_chain_ainvoke(
    client: WeaveClient,
) -> None:
    from langchain_core.prompts import PromptTemplate
    from langchain_openai import ChatOpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "sk-1234567890abcdef1234567890abcdef")

    llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=api_key, temperature=0.0)
    prompt = PromptTemplate.from_template("1 + {number} = ")

    llm_chain = prompt | llm
    _ = await llm_chain.ainvoke({"number": 2})

    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert_correct_calls_for_chain_invoke(calls)


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_simple_chain_stream(
    client: WeaveClient,
) -> None:
    from langchain_core.prompts import PromptTemplate
    from langchain_openai import ChatOpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "sk-1234567890abcdef1234567890abcdef")

    llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=api_key, temperature=0.0)
    prompt = PromptTemplate.from_template("1 + {number} = ")

    llm_chain = prompt | llm
    for _ in llm_chain.stream({"number": 2}):
        pass

    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert_correct_calls_for_chain_invoke(calls)


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
@pytest.mark.asyncio
@pytest.mark.skip
async def test_simple_chain_astream(
    client: WeaveClient,
) -> None:
    from langchain_core.prompts import PromptTemplate
    from langchain_openai import ChatOpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "sk-1234567890abcdef1234567890abcdef")

    llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=api_key, temperature=0.0)
    prompt = PromptTemplate.from_template("1 + {number} = ")

    llm_chain = prompt | llm
    async for _ in llm_chain.astream({"number": 2}):
        pass

    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert_correct_calls_for_chain_invoke(calls)


def assert_correct_calls_for_chain_batch(calls: list[Call]) -> None:
    flattened = flatten_calls(calls)
    assert len(flattened) == 8
    assert_ends_and_errors(flattened)

    got = [(op_name_from_ref(c.op_name), d, c.parent_id) for (c, d) in flattened]
    ids = [c.id for (c, _) in flattened]

    exp = [
        ("langchain.Chain.RunnableSequence", 0, None),
        ("langchain.Prompt.PromptTemplate", 1, ids[0]),
        ("langchain.Llm.ChatOpenAI", 1, ids[0]),
        ("openai.chat.completions.create", 2, ids[2]),
        ("langchain.Chain.RunnableSequence", 0, None),
        ("langchain.Prompt.PromptTemplate", 1, ids[4]),
        ("langchain.Llm.ChatOpenAI", 1, ids[4]),
        ("openai.chat.completions.create", 2, ids[6]),
    ]
    assert got == exp


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_simple_chain_batch(client: WeaveClient) -> None:
    from langchain_core.prompts import PromptTemplate
    from langchain_openai import ChatOpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "sk-1234567890abcdef1234567890abcdef")

    llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=api_key, temperature=0.0)
    prompt = PromptTemplate.from_template("1 + {number} = ")

    llm_chain = prompt | llm
    _ = llm_chain.batch([{"number": 2}, {"number": 3}])

    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert_correct_calls_for_chain_batch(calls)


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
@pytest.mark.asyncio
@pytest.mark.skip  # TODO: remove this once the langchain issue is fixed
async def test_simple_chain_abatch(
    client: WeaveClient,
) -> None:
    from langchain_core.prompts import PromptTemplate
    from langchain_openai import ChatOpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "sk-1234567890abcdef1234567890abcdef")

    llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=api_key, temperature=0.0)
    prompt = PromptTemplate.from_template("1 + {number} = ")

    llm_chain = prompt | llm
    _ = await llm_chain.abatch([{"number": 2}, {"number": 3}])

    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert_correct_calls_for_chain_batch(calls)


def assert_correct_calls_for_chain_batch_from_op(calls: list[Call]) -> None:
    flattened = flatten_calls(calls)
    assert len(flattened) == 9
    assert_ends_and_errors(flattened)

    got = [(op_name_from_ref(c.op_name), d, c.parent_id) for (c, d) in flattened]
    ids = [c.id for (c, _) in flattened]

    exp = [
        ("run_batch", 0, None),
        ("langchain.Chain.RunnableSequence", 1, ids[0]),
        ("langchain.Prompt.PromptTemplate", 2, ids[1]),
        ("langchain.Llm.ChatOpenAI", 2, ids[1]),
        ("openai.chat.completions.create", 3, ids[3]),
        ("langchain.Chain.RunnableSequence", 1, ids[0]),
        ("langchain.Prompt.PromptTemplate", 2, ids[5]),
        ("langchain.Llm.ChatOpenAI", 2, ids[5]),
        ("openai.chat.completions.create", 3, ids[7]),
    ]
    assert got == exp


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_simple_chain_batch_inside_op(client: WeaveClient) -> None:
    # This test is the same as test_simple_chain_batch, but ensures things work when nested in an op
    from langchain_core.prompts import PromptTemplate
    from langchain_openai import ChatOpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "sk-1234567890abcdef1234567890abcdef")

    llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=api_key, temperature=0.0)
    prompt = PromptTemplate.from_template("1 + {number} = ")

    llm_chain = prompt | llm

    @weave.op
    def run_batch(batch: list) -> None:
        _ = llm_chain.batch(batch)

        # assert call stack is properly constructed, during runtime
        parent = call_context.get_current_call()
        assert parent is not None
        assert "run_batch" in parent.op_name
        assert parent.parent_id is None
        assert len(parent.children()) == 2
        for child in parent.children():
            assert "langchain.Chain.RunnableSequence" in child.op_name
            assert child.parent_id == parent.id

            grandchildren = child.children()
            assert len(grandchildren) == 2
            assert "langchain.Prompt.PromptTemplate" in grandchildren[0].op_name
            assert grandchildren[0].parent_id == child.id
            assert "langchain.Llm.ChatOpenAI" in grandchildren[1].op_name
            assert grandchildren[1].parent_id == child.id

    run_batch([{"number": 2}, {"number": 3}])

    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert_correct_calls_for_chain_batch_from_op(calls)


def assert_correct_calls_for_rag_chain(calls: list[Call]) -> None:
    flattened = flatten_calls(calls)
    assert len(flattened) == 12
    assert_ends_and_errors(flattened)

    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]

    exp = [
        ("openai.embeddings.create", 0),
        ("langchain.Chain.RunnableSequence", 0),
        ("langchain.Chain.RunnableParallel_context_question", 1),
        ("langchain.Chain.RunnableSequence", 2),
        ("langchain.Retriever.VectorStoreRetriever", 3),
        ("openai.embeddings.create", 4),
        ("langchain.Chain.format_docs", 3),
        ("langchain.Chain.RunnablePassthrough", 2),  # Potential position
        ("langchain.Prompt.ChatPromptTemplate", 1),
        ("langchain.Llm.ChatOpenAI", 1),
        ("openai.chat.completions.create", 2),
        ("langchain.Parser.StrOutputParser", 1),
    ]
    # exp_2 is an alternative to exp with a different order of operations.
    # The `RunnableParallel_context_question` executes its children in parallel,
    # allowing for variation in the order of execution. As a result,
    # `RunnablePassthrough` may appear in one of two possible positions.
    exp_2 = [
        ("openai.embeddings.create", 0),
        ("langchain.Chain.RunnableSequence", 0),
        ("langchain.Chain.RunnableParallel_context_question", 1),
        ("langchain.Chain.RunnablePassthrough", 2),  # Potential position
        ("langchain.Chain.RunnableSequence", 2),
        ("langchain.Retriever.VectorStoreRetriever", 3),
        ("openai.embeddings.create", 4),
        ("langchain.Chain.format_docs", 3),
        ("langchain.Prompt.ChatPromptTemplate", 1),
        ("langchain.Llm.ChatOpenAI", 1),
        ("openai.chat.completions.create", 2),
        ("langchain.Parser.StrOutputParser", 1),
    ]
    assert (got == exp) or (got == exp_2)


@pytest.fixture
def fix_chroma_ci() -> Generator[None, None, None]:
    # According to https://docs.trychroma.com/troubleshooting#sqlite
    # which references https://gist.github.com/defulmere/8b9695e415a44271061cc8e272f3c300,
    # on Linux machines (CI runners), we need to patch sqlite3 to pysqlite3 and ensure
    # pysqlite3 is installed.
    if not os.environ.get("CI"):
        yield None
        return

    __import__("pysqlite3")
    import sys

    old = sys.modules["sqlite3"]
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
    try:
        yield None
    finally:
        sys.modules["sqlite3"] = old


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_simple_rag_chain(client: WeaveClient, fix_chroma_ci: None) -> None:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.document_loaders import TextLoader
    from langchain_community.vectorstores import Chroma
    from langchain_core.documents import Document
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnablePassthrough
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    loader = TextLoader("integrations/langchain/test_data/paul_graham_essay.txt")
    docs = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)

    api_key = os.environ.get("OPENAI_API_KEY", "sk-1234567890abcdef1234567890abcdef")

    vectorstore = Chroma.from_documents(
        documents=splits, embedding=OpenAIEmbeddings(openai_api_key=api_key)
    )
    retriever = vectorstore.as_retriever()

    prompt = ChatPromptTemplate.from_template(
        "You are an assistant for question-answering tasks. "
        "Use the following pieces of retrieved context to answer the question. "
        "If you don't know the answer, just say that you don't know. "
        "Use three sentences maximum and keep the answer concise.\n"
        "Question: {question}\nContext: {context}\nAnswer:"
    )

    llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=api_key, temperature=0.0)

    def format_docs(documents: list[Document]) -> str:
        return "\n\n".join(doc.page_content for doc in documents)

    # Chain
    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    rag_chain.invoke(
        input="What is the essay about?",
    )

    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert_correct_calls_for_rag_chain(calls)


def assert_correct_calls_for_agent_with_tool(calls: list[Call]) -> None:
    flattened = flatten_calls(calls)
    assert len(flattened) == 10
    assert_ends_and_errors(flattened)

    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]

    exp = [
        ("langchain.Chain.AgentExecutor", 0),
        ("langchain.Chain.RunnableSequence", 1),
        ("langchain.Chain.RunnableParallel_input_chat_history_agent_scratchpad", 2),
        ("langchain.Chain.RunnableLambda", 3),
        ("langchain.Chain.RunnableLambda", 3),
        ("langchain.Chain.RunnableLambda", 3),
        ("langchain.Prompt.ChatPromptTemplate", 2),
        ("langchain.Llm.ChatOpenAI", 2),
        ("openai.chat.completions.create", 3),
        ("langchain.Parser.OpenAIFunctionsAgentOutputParser", 2),
    ]
    assert got == exp


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_agent_run_with_tools(
    client: WeaveClient,
) -> None:
    from langchain.agents import AgentExecutor
    from langchain.agents.format_scratchpad import format_to_openai_function_messages
    from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
    from langchain.pydantic_v1 import BaseModel, Field
    from langchain.tools import StructuredTool
    from langchain_core.messages import AIMessage, HumanMessage
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_core.utils.function_calling import convert_to_openai_tool
    from langchain_openai import ChatOpenAI

    class CalculatorInput(BaseModel):
        a: int = Field(description="first number")
        b: int = Field(description="second number")

    def multiply(a: int, b: int) -> int:
        """Multiply two numbers."""
        return a * b

    calculator = StructuredTool.from_function(
        func=multiply,
        name="Calculator",
        description="multiply numbers",
        args_schema=CalculatorInput,
        return_direct=True,
    )

    api_key = os.environ.get("OPENAI_API_KEY", "sk-1234567890abcdef1234567890abcdef")

    llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=api_key, temperature=0.0)

    tools = [calculator]
    functions = [convert_to_openai_tool(t) for t in tools]

    assistant_system_message = """You are a helpful assistant. \
    Use tools (only if necessary) to best answer the users questions."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", assistant_system_message),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    llm_with_tools = llm.bind(tools=functions)

    def _format_chat_history(chat_history: list[tuple[str, str]]) -> list:
        buffer = []
        for human, ai in chat_history:
            buffer.append(HumanMessage(content=human))
            buffer.append(AIMessage(content=ai))
        return buffer

    agent = (
        {
            "input": lambda x: x["input"],
            "chat_history": lambda x: _format_chat_history(x["chat_history"]),
            "agent_scratchpad": lambda x: format_to_openai_function_messages(
                x["intermediate_steps"]
            ),
        }
        | prompt
        | llm_with_tools
        | OpenAIFunctionsAgentOutputParser()
    )

    class AgentInput(BaseModel):
        input: str
        chat_history: list[tuple[str, str]] = Field(
            ...,
            extra={"widget": {"type": "chat", "input": "input", "output": "output"}},
        )

    agent_executor = AgentExecutor(agent=agent, tools=tools).with_types(
        input_type=AgentInput
    )

    _ = agent_executor.invoke(
        {"input": "What is 3 times 4 ?", "chat_history": []},
    )
    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert_correct_calls_for_agent_with_tool(calls)


def assert_correct_calls_for_agent_with_function_call(calls: list[Call]) -> None:
    flattened = flatten_calls(calls)
    assert len(flattened) == 11
    assert_ends_and_errors(flattened)

    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]

    exp = [
        ("langchain.Chain.AgentExecutor", 0),
        ("langchain.Chain.RunnableSequence", 1),
        ("langchain.Chain.RunnableParallel_input_chat_history_agent_scratchpad", 2),
        ("langchain.Chain.RunnableLambda", 3),
        ("langchain.Chain.RunnableLambda", 3),
        ("langchain.Chain.RunnableLambda", 3),
        ("langchain.Prompt.ChatPromptTemplate", 2),
        ("langchain.Llm.ChatOpenAI", 2),
        ("openai.chat.completions.create", 3),
        ("langchain.Parser.OpenAIFunctionsAgentOutputParser", 2),
        ("langchain.Tool.Calculator", 1),
    ]
    assert got == exp


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_agent_run_with_function_call(
    client: WeaveClient,
) -> None:
    from langchain.agents import AgentExecutor
    from langchain.agents.format_scratchpad import format_to_openai_function_messages
    from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
    from langchain.pydantic_v1 import BaseModel, Field
    from langchain.tools import StructuredTool
    from langchain_core.messages import AIMessage, HumanMessage
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_core.utils.function_calling import convert_to_openai_function
    from langchain_openai import ChatOpenAI

    class CalculatorInput(BaseModel):
        a: int = Field(description="first number")
        b: int = Field(description="second number")

    def multiply(a: int, b: int) -> int:
        """Multiply two numbers."""
        return a * b

    calculator = StructuredTool.from_function(
        func=multiply,
        name="Calculator",
        description="multiply numbers",
        args_schema=CalculatorInput,
        return_direct=True,
    )

    api_key = os.environ.get("OPENAI_API_KEY", "sk-1234567890abcdef1234567890abcdef")

    llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=api_key, temperature=0.0)

    tools = [calculator]
    functions = [convert_to_openai_function(t) for t in tools]

    assistant_system_message = """You are a helpful assistant. \
        Use tools (only if necessary) to best answer the users questions."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", assistant_system_message),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    llm_with_tools = llm.bind(functions=functions)

    def _format_chat_history(chat_history: list[tuple[str, str]]) -> list:
        buffer = []
        for human, ai in chat_history:
            buffer.append(HumanMessage(content=human))
            buffer.append(AIMessage(content=ai))
        return buffer

    agent = (
        {
            "input": lambda x: x["input"],
            "chat_history": lambda x: _format_chat_history(x["chat_history"]),
            "agent_scratchpad": lambda x: format_to_openai_function_messages(
                x["intermediate_steps"]
            ),
        }
        | prompt
        | llm_with_tools
        | OpenAIFunctionsAgentOutputParser()
    )

    class AgentInput(BaseModel):
        input: str
        chat_history: list[tuple[str, str]] = Field(
            ...,
            extra={"widget": {"type": "chat", "input": "input", "output": "output"}},
        )

    agent_executor = AgentExecutor(agent=agent, tools=tools).with_types(
        input_type=AgentInput
    )

    _ = agent_executor.invoke(
        {"input": "What is 3 times 4 ?", "chat_history": []},
    )
    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert_correct_calls_for_agent_with_function_call(calls)


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_weave_attributes_in_call(client: WeaveClient) -> None:
    from langchain_core.prompts import PromptTemplate
    from langchain_openai import ChatOpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "sk-1234567890abcdef1234567890abcdef")

    llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=api_key, temperature=0.0)
    prompt = PromptTemplate.from_template("1 + {number} = ")

    llm_chain = prompt | llm
    with weave.attributes({"call_attr": 1}):
        _ = llm_chain.invoke({"number": 2})

    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert len(calls) > 0
    call_attrs = calls[0].attributes
    assert call_attrs["call_attr"] == 1
    assert "lc_id" in call_attrs
    assert "parent_run_id" in call_attrs
    assert "lc_name" in call_attrs


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key", "x-goog-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai", "*.googleapis.com"],
    before_record_request=filter_body,
    match_on=["method", "scheme", "path", "query"],
)
def test_langchain_google_vertexai_usage(client: WeaveClient) -> None:
    from google.auth.credentials import AnonymousCredentials
    from langchain_google_vertexai import ChatVertexAI

    with patch(
        "google.auth.default", return_value=(AnonymousCredentials(), "wandb-qa")
    ):
        llm = ChatVertexAI(
            model="gemini-2.5-pro-preview-05-06",
            temperature=0,
            max_tokens=None,
            max_retries=2,
            api_transport="rest",
            credentials=AnonymousCredentials(),
        )

        messages = [
            (
                "system",
                "Talk like Geralt of Rivia.",
            ),
            ("human", "What do you do?"),
        ]

        llm.invoke(messages)

    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert len(calls) > 0
    call = calls[0]
    # Assert that the call has usage metadata
    assert call.summary is not None
    assert "usage" in call.summary
    assert "gemini-2.5-pro-preview-05-06" in call.summary["usage"].unwrap()


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
    match_on=["method", "scheme", "path", "query"],
)
def test_langchain_google_genai_usage(client: WeaveClient) -> None:
    from langchain_google_genai import GoogleGenerativeAI

    llm = GoogleGenerativeAI(
        model="gemini-1.5-pro",
        transport="rest",
        google_api_key="fake-key",
    )

    llm.invoke(
        [
            ("system", "Talk like Geralt of Rivia."),
            ("human", "what do you think about the future of AI?"),
        ]
    )

    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert len(calls) > 0
    call = calls[0]
    # Assert that the call has usage metadata
    assert call.summary is not None
    assert "usage" in call.summary
    assert "gemini-1.5-pro-002" in call.summary["usage"].unwrap()


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_langchain_anthropic_usage(client: WeaveClient) -> None:
    from langchain_anthropic import ChatAnthropic

    model = ChatAnthropic(
        model="claude-opus-4-20250514",
        anthropic_api_key="sk-ant-api03-fake-key",
    )

    model.invoke(
        [
            (
                "system",
                "Talk like Geralt of Rivia.",
            ),
            (
                "human",
                "Are semicolons optional in JavaScript? You should also reasonate why as a witcher, you know about JavaScript.",
            ),
        ]
    )

    calls = list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))
    assert len(calls) > 0
    call = calls[0]
    # Assert that the call has usage metadata
    assert call.summary is not None
    assert "usage" in call.summary
    assert "claude-opus-4-20250514" in call.summary["usage"].unwrap()
