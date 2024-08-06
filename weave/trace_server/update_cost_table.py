# script to load data into llm_token_prices table in ClickHouse
from datetime import datetime

import requests

# Load the data
url = "https://raw.githubusercontent.com/AgentOps-AI/tokencost/main/tokencost/model_prices.json"
req = requests.get(url)

if req.status_code != requests.codes.ok:
    print("Token cost file was not found.")
    exit()

data = req.json()

# ClickHouse HTTP interface details
clickhouse_url = "http://localhost:8123"
headers = {"Content-Type": "application/json"}

# Create the llm_token_prices table with pricing_level instead of type
create_table_query = """
CREATE TABLE IF NOT EXISTS llm_token_prices (
    pricing_level String,
    pricing_level_id String,
    provider_id String,
    llm_id String,
    effective_date DateTime64(3),
    prompt_token_cost Float32,
    completion_token_cost Float32,
    inserted_by String DEFAULT 'system',
    inserted_at DateTime64(3) DEFAULT now()
) ENGINE = ReplacingMergeTree()
ORDER BY (pricing_level, pricing_level_id, llm_id, effective_date)
"""

response = requests.post(clickhouse_url, data=create_table_query, headers=headers)
if response.status_code != 200:
    print("Error creating table:", response.text)
    exit(1)

# Prepare the data for insertion
insert_data_query = "INSERT INTO llm_token_prices (pricing_level, pricing_level_id, provider_id, llm_id, effective_date, prompt_token_cost, prompt_token_cost_unit, completion_token_cost, completion_token_cost_unit, inserted_by, inserted_at) VALUES "
values = []

for llm_id, details in data.items():
    input_token_cost = details.get("input_cost_per_token", 0)
    output_token_cost = details.get("output_cost_per_token", 0)
    litellm_provider_id = details.get("litellm_provider", "default")
    values.append(
        f"('default', 'default', '{litellm_provider_id}', '{llm_id}', '{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}', {input_token_cost}, 'USD', {output_token_cost}, 'USD', 'system', now())"
    )

insert_data_query += ", ".join(values)

# Insert the data into the table
response = requests.post(clickhouse_url, data=insert_data_query, headers=headers)
if response.status_code != 200:
    print("Error inserting data:", response.text)
else:
    print("Data insertion completed.")
