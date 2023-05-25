from json import load, dumps
from sys import argv
# import pyarrow.dataset as ds
import pyarrow as pa
from weave.profile import getsize_mb
from typing import Any, Optional, Union, TypedDict

FILENAME = "weavepythoncg.json"
JSON_KEY = "sampledHistorySubset"

def main():
    data = load_json_file(FILENAME)
    json = recurse_to_key(data, JSON_KEY)
    if json is None:
        print(f"Could not find key {JSON_KEY}")
        return
    
    json = convert_nums_to_strs(json)

    print(f"Json size: {getsize_mb(json)}")

    history_v0 = to_historyv0(json)
    print(f"HistoryV0 size: {getsize_mb(history_v0)}")

    history_v1 = to_historyv1(history_v0)
    print(f"HistoryV1 size: {getsize_mb(history_v1)}")

    json_str = dumps(json, separators=(',', ':'))
    print(f"Json string size: {getsize_mb(json_str)}")

    history_v0_str = dumps(history_v0, separators=(',', ':'))
    print(f"HistoryV0 string size: {getsize_mb(history_v0_str)}")

    history_v1_str = dumps(history_v1, separators=(',', ':'))
    print(f"HistoryV1 string size: {getsize_mb(history_v1_str)}")

    arrow_table = to_arrow_table(history_v0)
    print(f"Arrow table size: {getsize_mb(arrow_table)}")

    arrow_array = to_arrow_array(history_v1)
    print(f"Arrow array size: {getsize_mb(arrow_array)}")

Json = list[list[dict[str, Any]]]

HistoryV0 = dict[int, dict[str, Any]]

def to_historyv0(json: Json) -> HistoryV0:
    history: HistoryV0 = {}
    
    for col_data in json:
        for row in col_data:
            step = row["_step"]
            history_row = history.setdefault(step, {})
            for col in row:
                if col == "_step":
                    continue
                history_row[col] = row[col]

    return history

HistoryV1 = list[dict[str, Any]]

def to_historyv1(history_v0: HistoryV0) -> HistoryV1:
    history: HistoryV1 = []

    steps = sorted(history_v0.keys())
    for step in steps:
        history_row = history_v0[step].copy()
        history_row["_step"] = step
        history.append(history_row)

    return history

def to_arrow_table(history_v0: HistoryV0):
    copy = {}
    for step in history_v0:
        copy[str(step)] = history_v0[step]
    return pa.table(copy)

def to_arrow_array(history_v1: HistoryV1):
    return pa.array(history_v1)

def recurse_to_key(obj: Union[dict[str, Any], list[Any]], key: str) -> Optional[Json]:
    if isinstance(obj, list):
        for item in obj:
            if not isinstance(item, dict):
                continue
            res = recurse_to_key(item, key)
            if res is not None:
                return res
        return
    
    for k in obj:
        if k == key:
            return obj[k]
        
    for k in obj:
        if not (isinstance(obj[k], dict) or isinstance(obj[k], list)):
            continue
        res = recurse_to_key(obj[k], key)
        if res is not None:
            return res
        
def convert_nums_to_strs(json: Json) -> Json:
    converted = json.copy()

    for col_data in converted:
        for row in col_data:
            for k in row:
                if k == "_step":
                    continue
                if isinstance(row[k], int) or isinstance(row[k], float):
                    row[k] = str(row[k])

    return converted
    
def load_json_file(file_path: str):
    with open(file_path, 'r') as file:
        data = load(file)
    return data

# def read_parquet():
#     schema = ds.dataset("0000.parquet").schema
#     print(schema)

main()