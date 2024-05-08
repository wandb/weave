# import os

# os.environ["WF_TRACE_SERVER_URL"] = "http://127.0.0.1:6345"


# import weave


# weave.init('2024-05-08_callstest')

# @weave.op
# def say_hello(name: str):
#     print(f"hi {name}")
#     return name + name

# say_hello('jamie')
# call = next(iter(say_hello.calls()))._val

# # call.feedback.add('note', wassup="wassup with you")
# # call.feedback.thumbs_up()

# #x = call.feedback._repr_html_()
# print(call.feedback)

# #x = str(call.feedback)
# #print(call.feedback)

import json
from typing import Any

import requests


def test_create_feedback(body: dict[str, Any]):
    url = 'http://127.0.0.1:6345/feedback/create'
    auth = requests.utils.get_netrc_auth('https://api.wandb.ai')
    response = requests.post(url, json=body, auth=auth)
    print('Status code:', response.status_code)
    print(json.dumps(response.json(), indent=4))


def test_query_feedback(body: dict[str, Any]):
    url = 'http://127.0.0.1:6345/feedback/query'
    auth = requests.utils.get_netrc_auth('https://api.wandb.ai')
    response = requests.post(url, json=body, auth=auth)
    print('Status code:', response.status_code)
    print(json.dumps(response.json(), indent=4))


def test_purge_feedback(body: dict[str, Any]):
    url = 'http://127.0.0.1:6345/feedback/purge'
    auth = requests.utils.get_netrc_auth('https://api.wandb.ai')
    response = requests.post(url, json=body, auth=auth)
    print('Status code:', response.status_code)
    print(json.dumps(response.json(), indent=4))



# body = {
#     'project_id': 'jamie-rasmussen/2025-05-30_mongo',
#     'weave_ref': 'weave:///...',
#     'feedback_type': 'custom',
#     'payload': {
#         'key': 'value',
#     },
# }
# test_create_feedback(body)


body = {
    'project_id': 'jamie-rasmussen/2025-05-30_mongo',
    'weave_ref': 'weave:///...',
    'feedback_type': 'wandb.reaction.1',
    'payload': {
    #    'emoji': '🫱🏿‍🫲🏽',
       'emoji': '🧑🏼‍⚖️',
    },
}
#test_create_feedback(body)

body = {
    'project_id': 'jamie-rasmussen/2025-05-30_mongo',
    'weave_ref': 'weave:///...',
    'feedback_type': 'wandb.note.1',
    'payload': {
        'note': 'another note',
    },
}
#test_create_feedback(body)

# test_purge_feedback({
#     'project_id': 'jamie-rasmussen/2025-05-30_mongo',
#     'query': {
#         '$expr': {
#             "$eq": [
#                 {"$getField": "id"},
#                 {"$literal": "11650064-7ad5-4545-9bfa-1c29af698d14"},
#             ],
#         }
#     }
# })


res = test_query_feedback({
    'project_id': 'jamie-rasmussen/2024-05-31_values',
    # 'fields': ['id', 'payload.note'],
    'query': {
        '$expr': {
            "$eq": [
                {"$getField": "feedback_type"},
                {"$literal": "wandb.note.1"},
            ],
        }
    },
    'sort_by': [
        {
            "field": "payload.note",
            "direction": "desc",
        },
    ],
    # 'offset': 1,
    # 'limit': 1,
})
print(res)
