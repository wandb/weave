import os
import weave
import google.generativeai as genai


weave.init(project_name="google_ai_studio-test")

genai.configure(api_key=os.getenv("GOOGLE_GENAI_KEY"))
model = genai.GenerativeModel(model_name="gemini-1.5-pro", tools="code_execution")
chat = model.start_chat()
chat.send_message(
    "What is the sum of the first 50 prime numbers? "
    "Generate and run code for the calculation, and make sure you get all 50."
)
