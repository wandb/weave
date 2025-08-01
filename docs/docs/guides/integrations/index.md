# Integrations

:::success[Automatic Tracking]
In most cases, all you need to do is call `weave.init()` at the top of your script or program in order for Weave to automatically patch and track any of these libraries!
:::

Weave provides automatic logging integrations for popular LLM providers and orchestration frameworks. These integrations allow you to seamlessly trace calls made through various libraries, enhancing your ability to monitor and analyze your AI applications.

## LLM Providers

LLM providers are the vendors that offer access to large language models for generating predictions. Weave integrates with these providers to log and trace the interactions with their APIs:

- **[W&B Inference Service](/guides/integrations/inference)**
- **[Amazon Bedrock](/guides/integrations/bedrock)**
- **[Anthropic](/guides/integrations/anthropic)**
- **[Cerebras](/guides/integrations/cerebras)**
- **[Cohere](/guides/integrations/cohere)**
- **[Google](/guides/integrations/google)**
- **[Groq](/guides/integrations/groq)**
- **[Hugging Face Hub](/guides/integrations/huggingface)**
- **[LiteLLM](/guides/integrations/litellm)**
- **[Microsoft Azure](/guides/integrations/azure)**
- **[MistralAI](/guides/integrations/mistral)**
- **[NVIDIA NIM](/guides/integrations/nvidia_nim)**
- **[OpenAI](/guides/integrations/openai)**
- **[Open Router](/guides/integrations/openrouter)**
- **[Together AI](/guides/integrations/together_ai)**

**[Local Models](/guides/integrations/local_models)**: For when you're running models on your own infrastructure.

## Frameworks

Frameworks help orchestrate the actual execution pipelines in AI applications. They provide tools and abstractions for building complex workflows. Weave integrates with these frameworks to trace the entire pipeline:

- **[OpenAI Agents SDK](/guides/integrations/openai_agents)**
- **[LangChain](/guides/integrations/langchain)**
- **[LlamaIndex](/guides/integrations/llamaindex)**
- **[DSPy](/guides/integrations/dspy)**
- **[Instructor](/guides/integrations/instructor)**
- **[CrewAI](/guides/integrations/crewai)**
- **[Smolagents](/guides/integrations/smolagents)**
- **[PydanticAI](/guides/integrations/pydantic_ai)**
- **[Google Agent Development Kit (ADK)](/guides/integrations/google_adk)**
- **[AutoGen](/guides/integrations/autogen)**
- **[Verdict](/guides/integrations/verdict)**
- **[TypeScript SDK](/guides/integrations/js)**
- **[Agno](/guides/integrations/agno.md)**

## Protocols

Weave integrates with standardized protocols that enable communication between AI applications and their supporting services:

- **[Model Context Protocol (MCP)](/guides/integrations/mcp)**

Choose an integration from the lists above to learn more about how to use Weave with your preferred LLM provider, framework, or protocol. Whether you're directly accessing LLM APIs, building complex pipelines, or using standardized protocols, Weave provides the tools to trace and analyze your AI applications effectively.
