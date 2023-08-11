import datetime
import json


def append_json_to_file(json_data: dict, file_name: str = "/tmp/weave.log") -> None:
    with open(file_name, "a+") as outfile:
        str_data = json.dumps(json_data)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:%f")
        outfile.write(f"{timestamp} :: {str_data}\n")
