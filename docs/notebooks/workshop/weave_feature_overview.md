## 🐝 Weave Features Overview

### 🔍 **Tracing & Observability**
**SDK Features:**
- `@weave.op` decorator for automatic function tracing
- Auto-patching for LLM libraries

**Application Features:**
- **Trace Viewer**
  - Tree view of nested calls
  - Code view with source
  - Flame graph for performance analysis
  - Timeline sliders for filtering
- **Call Details**
  - Cost tracking
  - Token usage metrics
  - Latency measurements
  - Source code tracking
  - Inputs/outputs capture
  - Exception and error tracking
- **LLM Completions**
  - "Time travel" - Open any past LLM call in playground
  - Replay and modify historical calls
- **Media Type Support**
  - Images, audio, video rendering
- **OpenTelemetry (OTEL) Integration**

### 📊 **Traces Table & Analysis**
- **Saved Views** - Save filter/sort configurations
- **Advanced Filtering & Sorting**
- **Export Options**
  - Python code export
  - File downloads (CSV, JSON)
  - cURL commands for API access

### 🎮 **Playground**
- **Saved Prompts** - Version and reuse prompts
- **Multi-Model Comparisons** - Compare outputs side-by-side
- **Custom Model Integration** - Add your own models

### 📈 **Evaluations**
**Views & Analytics:**
- **Single Evaluation Results**
  - Score summaries
  - Predict & score detailed table
- **Evaluation Runs List** - Historical view of all evals
- **Comparison Report**
  - Single eval Report
  - Multi-eval Report w/ Regression Finding Tools
- **Leaderboards**
  - Automatic leaderboard per evaluation
  - Configurable Global leaderboard across evaluations

**SDK Options:**
- Standard `Evaluation` API
- Flexible `EvaluationLogger` API

### 🛡️ **Production Monitoring**
**SDK Features:**
- **Guardrails** - Real-time content filtering
- **Monitors** - Passive quality tracking
- **Scorers** - Flexible scoring system

**Application Features:**
- **Human Feedback** - Expert annotations
- **Dataset Building** - Add production examples to datasets

### 💾 **Core Objects (Version Control)**
Save, version, and compare:
- **Datasets** - Test sets and examples
- **Models** - Model configurations and parameters  
- **Prompts** - Prompt templates and variations
