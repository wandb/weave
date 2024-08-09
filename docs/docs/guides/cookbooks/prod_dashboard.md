---
sidebar_position: 2
hide_table_of_contents: true
---

# Integrating with Weave: Case Study - Custom Dashboard for Production Monitoring
When we consider how well Weave can be intergated in existing processes and AI Apps we consider data input and data output as the two fundemantal characteristics:
1.  **Data Input:** 
    * **Framework Agnostic Tracing:** Many different tools, packages, frameworks are used to create LLM apps (LangChain, LangGraph, LlamaIndex, AutoGen, CrewAI). Weave's single `@weave-op()` decorator makes it very easy to integrate with any framework and custom objects (THERE SHOULD BE A COOKBOOK FOR HOW TO INTEGRATE AND HOW TO DEAL WITH CUSTOM OBJECTS INCL. SERIALIZATION). For most common frameworks our team already did that making the tracking of apps as easy as initializing Weave before the start of the application. For how feedback can be flexibly integrated into Weave check out the Cookbook Series on Feedback (ADD LINK TO OTHER COOKBOOK HERE).
    * **Openning API endpoints (soon):** LLM applications are very diverse (webpage in typescript, python scripts, java backends, on-device apps) but should still be trckable and traceable from anywhere. For most use-cases Weave is already proving native support (python and typescript coming soon), for the rest Weave makes it very easy to log traces or connect with existing tools (ONE AVAILABLE A COOKBOOK SHOULD BE LAUNCHED ONCE THE NEW APIs ARE EXPOSED).

2. **Data Output**: Weave focuses on a) online monitoring (tracing generations, tracking governance metrics such as cost, latency, tokens) and b) offline evaluations (systematic benchmarking on eval datasets, human feedback loops, LLM judges, side-by-side comparisons). For both parts Weave provides strong visulalization capabiltities through the Weave UI. Sometimes, creating a visual extension based on the specific business or monitoring requirements makes sense - this is what we'll discover in this cookbook (SEEMS LIKE IN THE FUTURE WE'LL HAVE WEAVE BOARDS BACK FOR THAT).

The introduction, specific use-case that we consider in this cookbook:
* In  this cookbook we show how Weave's exposed APIs and functions make it very easy to create a custom dashboard for production monitoring as an extension to the Traces view in Weave. 
* We will focus on creating aggregate views of the cost, latency, tokens, and provided user-feedback
* We will focus on providing aggregation functions across models, calls, and projects
* We will take a look at how to add alerts and guardrailes (GOOD FOR OTHER COOKBOOKS)