import asyncio
from google import genai
import weave
from pydantic import BaseModel


weave.init(project_name="gemini-test")
client = genai.Client(api_key="AIzaSyBiYf-E95RSI7bUeZL-3JyPd16N2Fd1YF8")

# response = client.models.generate_content(
#     model="gemini-2.0-flash-exp",
#     contents="Tell me a story about a lonely robot who finds friendship in a most unexpected place.",
# )

# print(type(response))

# count = 0
# for chunk in client.models.generate_content_stream(
#     model="gemini-2.0-flash-exp",
#     contents="Tell me a story about a lonely robot who finds friendship in a most unexpected place."
# ):
#     print(type(chunk))
#     count += 1
#     if count > 3:
#         break
#     # print("*****************")


async def generate_content():
    response = await client.aio.models.generate_content_stream(
        model="gemini-2.0-flash-exp",
        contents="Tell me a story about a lonely robot who finds friendship in a most unexpected place."
    )
    async for chunk in response:
        print(chunk.text, sep="", end="")

asyncio.run(generate_content())
