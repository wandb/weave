from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import langchain

# langchain.verbose = False
# langchain.debug = False

def test_langchain():
    llm = ChatOpenAI(api_key="...")
    result = llm.invoke("how can langsmith help with testing?")
    assert result == "Langsmith can help with testing by providing a platform for testing and debugging code."

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are world class technical documentation writer."),
        ("user", "{input}")
    ])

    chain = prompt | llm 

    chain.invoke({"input": "how can langsmith help with testing?"})

    assert chain.get_output() == "Langsmith can help with testing by providing a platform for testing and debugging code."

    output_parser = StrOutputParser()

    chain = prompt | llm | output_parser

    chain.invoke({"input": "how can langsmith help with testing?"})

    assert chain.get_output() == "Langsmith can help with testing by providing a platform for testing and debugging code."
