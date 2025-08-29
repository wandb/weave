"""
Example showing explicit patching for various integrations in Weave.

Instead of automatic patching on init, you now need to explicitly enable
tracing for each integration you want to use.
"""

import weave

# Initialize Weave
weave.init("my-project")

# Enable specific integrations by calling their patch functions

# LLM Providers
weave.patch_openai()  # OpenAI GPT models
weave.patch_anthropic()  # Claude models
weave.patch_mistral()  # Mistral models
weave.patch_groq()  # Groq inference
weave.patch_cohere()  # Cohere models
weave.patch_cerebras()  # Cerebras models
weave.patch_google_genai()  # Google Generative AI
weave.patch_vertexai()  # Google Vertex AI
weave.patch_huggingface()  # Hugging Face models

# Frameworks
weave.patch_litellm()  # LiteLLM unified interface
weave.patch_langchain()  # LangChain framework
weave.patch_llamaindex()  # LlamaIndex framework
weave.patch_dspy()  # DSPy framework
weave.patch_instructor()  # Instructor library
weave.patch_crewai()  # CrewAI agents
weave.patch_autogen()  # Microsoft AutoGen
weave.patch_smolagents()  # SmolAgents
weave.patch_openai_agents()  # OpenAI Agents SDK

# Other integrations
weave.patch_notdiamond()  # NotDiamond routing
weave.patch_verdict()  # Verdict evaluation
weave.patch_nvidia()  # NVIDIA AI endpoints
weave.patch_mcp()  # Model Context Protocol

# Now use any of the patched integrations
# Example with OpenAI:
from openai import OpenAI

client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4", messages=[{"role": "user", "content": "Hello!"}]
)

# Example with multiple integrations:
# If you've patched both OpenAI and Anthropic, both will be traced
import anthropic

claude = anthropic.Client()
# ... use claude client ...
