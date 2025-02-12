import asyncio
import os

import pytest

from weave.integrations.integration_utilities import op_name_from_ref


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_text_to_sql_agent(client):
    from sqlalchemy import (
        create_engine,
        MetaData,
        Table,
        Column,
        String,
        Integer,
        Float,
        insert,
        text,
    )
    from smolagents import tool, CodeAgent, OpenAIServerModel

    engine = create_engine("sqlite:///:memory:")
    metadata_obj = MetaData()

    def insert_rows_into_table(rows, table, engine=engine):
        for row in rows:
            stmt = insert(table).values(**row)
            with engine.begin() as connection:
                connection.execute(stmt)

    table_name = "receipts"
    receipts = Table(
        table_name,
        metadata_obj,
        Column("receipt_id", Integer, primary_key=True),
        Column("customer_name", String(16), primary_key=True),
        Column("price", Float),
        Column("tip", Float),
    )
    metadata_obj.create_all(engine)

    rows = [
        {"receipt_id": 1, "customer_name": "Alan Payne", "price": 12.06, "tip": 1.20},
        {"receipt_id": 2, "customer_name": "Alex Mason", "price": 23.86, "tip": 0.24},
        {"receipt_id": 3, "customer_name": "Woodrow Wilson", "price": 53.43, "tip": 5.43},
        {"receipt_id": 4, "customer_name": "Margaret James", "price": 21.11, "tip": 1.00},
    ]
    insert_rows_into_table(rows, receipts)

    @tool
    def sql_engine(query: str) -> str:
        """
        Allows you to perform SQL queries on the table. Returns a string representation of the result.
        The table is named 'receipts'. Its description is as follows:
            Columns:
            - receipt_id: INTEGER
            - customer_name: VARCHAR(16)
            - price: FLOAT
            - tip: FLOAT

        Args:
            query: The query to perform. This should be correct SQL.
        """
        output = ""
        with engine.connect() as con:
            rows = con.execute(text(query))
            for row in rows:
                output += "\n" + str(row)
        return output
    
    agent = CodeAgent(tools=[sql_engine],model=OpenAIServerModel("gpt-4o-mini"))
    answer = agent.run("Can you give me the name of the client who got the most expensive receipt?")
    assert "woodrow wilson" in answer.lower()

    calls = list(client.calls())
    assert len(calls) >= 9

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "smolagents.MultiStepAgent.run"
    assert "woodrow wilson" in call.output.lower()

    call = calls[1]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "smolagents.CodeAgent.step"

    call = calls[2]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "smolagents.MultiStepAgent.write_memory_to_messages"

    call = calls[3]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "smolagents.OpenAIServerModel"
    assert "Thought:" in call.output.content and "Code:" in call.output.content

    call = calls[4]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert "Thought:" in call.output["choices"][0]["message"]["content"] and "Code:" in call.output["choices"][0]["message"]["content"]
