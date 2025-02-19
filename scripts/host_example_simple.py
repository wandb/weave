import openai

import weave
from weave.trace.thread_host import ThreadPredictRequest, host_op

STATE_TYPE = list[dict]

thread_state: dict[str, STATE_TYPE] = {}

@weave.op()
async def predict(input: str, thread_id: str) -> str:
    curr_state = thread_state.get(thread_id, [])
    new_state = curr_state + [{"role": "user", "content": input}]
    thread_state[thread_id] = new_state
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=new_state,
    )
    res = response.choices[0].message.content
    final_state = new_state + [{"role": "assistant", "content": res}]
    thread_state[thread_id] = final_state
    return res


class PredictRequest(ThreadPredictRequest):
    input: str

weave.init("threading-demo")
host_op(PredictRequest, predict)
