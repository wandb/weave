import weave
weave.init("anthropic_project")

# use the anthropic library as usual
import os
from anthropic import Anthropic

client = Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY"),
)

message = client.messages.create(
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": "Tell me a joke about a dog",
        }
    ],
    model="claude-3-haiku-20240307",
)
print(message.content)

@weave.op()
def call_anthropic(user_input:str, model:str) -> str:
    message = client.messages.create(
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": user_input,
        }
        ],
        model=model,
    )
    return message.content[0].text

@weave.op()
def generate_joke(topic: str) -> str:
    return call_anthropic(f"Tell me a joke about {topic}", model="claude-3-haiku-20240307")

print(generate_joke("chickens"))
print(generate_joke("cars"))

