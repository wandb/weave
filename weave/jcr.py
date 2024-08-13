import weave
from weave import Prompt

weave.init("2024-09-09_quickstart")

prompt = Prompt(name="myprompt")
prompt.append("You are an expert in the field of travel advice.", role="system")
prompt.append("What's the capital of {country}?")

print(prompt.to_json())
# print(len(prompt))
# print(prompt[0])

# for message in prompt:
#     print(message)


weave.publish(prompt)


dataset = weave.Dataset(
    name="countries",
    rows=[
        {"id": "0", "country": "Australia", "capital": "Canberra"},
        {"id": "1", "country": "Brazil", "capital": "Brasília"},
        {"id": "2", "country": "Canada", "capital": "Ottawa"},
        {"id": "3", "country": "Denmark", "capital": "Copenhagen"},
        {"id": "4", "country": "Egypt", "capital": "Cairo"},
        {"id": "5", "country": "France", "capital": "Paris"},
        {"id": "6", "country": "Germany", "capital": "Berlin"},
        {"id": "7", "country": "Hungary", "capital": "Budapest"},
        {"id": "8", "country": "India", "capital": "New Delhi"},
        {"id": "9", "country": "Japan", "capital": "Tokyo"},
    ],
)
weave.publish(dataset)
