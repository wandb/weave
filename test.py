import os
import asyncio
import weave
import google.generativeai as genai


genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
weave.init(project_name="google-test")
model = genai.GenerativeModel("gemini-1.5-flash")

# ################ Sync No-Streaming ################
# response = model.generate_content("Write a story about an AI and magic")


# ################ Sync Streaming ################
# response = model.generate_content("Write a story about an AI and magic", stream=True)
# chunks = [chunk.text for chunk in response]
#
#
# ################ ASync non-Streaming ################
# async def async_generate():
#     response = await model.generate_content_async("Write a story about an AI and magic")
#     return response
#
#
# response = asyncio.run(async_generate())
#
#
################ Async Streaming ################
async def get_response():
    async for chunk in await model.generate_content_async(
        "Write a story about an AI and magic", stream=True
    ):
        if chunk.text:
            print(chunk.text)
        print("_" * 80)


response = asyncio.run(get_response())
