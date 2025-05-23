# 🐝 Weave Workshop - Instructor Guide

## Workshop Overview
**Duration**: 2-3 hours  
**Focus**: Hands-on experience with Weave features  
**Goal**: Participants leave knowing how to use Weave to build, debug, and evaluate LLM applications

## 🎯 Learning Objectives

By the end of this workshop, participants will be able to:
1. Use `@weave.op` to trace function calls
2. Debug LLM applications using Weave's UI
3. Build and run evaluations with both Evaluation and EvaluationLogger
4. Compare models systematically
5. Track and debug exceptions in production
6. Monitor applications with scorers as guardrails
7. Use Weave for cost and performance tracking

## 📋 Pre-Workshop Checklist

- [ ] Participants have W&B accounts
- [ ] OpenAI API keys ready (have backup keys)
- [ ] Workshop Python files downloaded
- [ ] Weave UI accessible
- [ ] Screen sharing setup tested
- [ ] Example traces pre-generated (optional)
- [ ] Decide on execution environment (notebook vs script)

## 🏃 Workshop Flow

### Introduction (10 mins)
- Welcome and introductions
- What is Weave and why use it?
- Quick UI tour (show a pre-made trace)
- Workshop overview

### Part 1: Tracing & Debugging (20 mins)
**Key Points:**
- `@weave.op` decorator auto-traces functions
- Every input/output is logged
- Traces appear in real-time in the UI

**Live Demo:**
- Run the customer email analyzer
- Show the trace in Weave UI
- Highlight inputs, outputs, latency

**Common Issues:**
- API key not set → Check environment variables
- Weave not initialized → Run `weave.init()`

### Part 2: Call Traces (15 mins)
**Key Points:**
- Nested function calls create trace trees
- Easy to debug complex pipelines
- See exactly where time is spent

**Activity:**
- Have participants modify the urgency classifier
- Add their own preprocessing step
- View the nested traces

### Part 3: Building Evaluations (30 mins)
**Key Points:**
- Datasets organize test examples
- Scorers measure performance
- Evaluations run systematically

**Hands-On:**
- Walk through creating scorers
- Run the evaluation together
- Explore results in the UI

**Teaching Tip:**
Show how the dataset is intentionally challenging to leave room for improvement

### Part 3b: EvaluationLogger (10 mins)
**Key Points:**
- Flexible incremental logging
- Perfect for streaming or custom workflows
- Handle errors gracefully
- **Critical**: Model and dataset identification is crucial since there are no objects
- Can use dictionaries for rich metadata (recommended!)

**Demo:**
- Show simple string identification vs dictionary identification
- Emphasize how dictionary metadata helps with filtering/comparison
- Show custom scoring logic
- Process examples one-by-one
- Add summary statistics

**Teaching Note:**
Emphasize that unlike standard Evaluation, EvaluationLogger relies entirely on the model and dataset parameters for identification. Show how dictionary metadata makes evaluations more discoverable and comparable.

### Part 4: Model Comparison (20 mins)
**Key Points:**
- Models encapsulate parameters
- Easy A/B testing
- Side-by-side comparisons in UI
- **Important**: Use ONE evaluation definition for all models

**Demo:**
- Show the three model variants (basic, detailed, balanced)
- Run evaluations on each
- Use Weave's comparison view
- Explain why we use the same evaluation object for all models:
  - Ensures fair comparison
  - Allows workshop participants to see aggregated results
  - Each run still gets a unique ID automatically

**Teaching Note:**
Emphasize that the evaluation definition (dataset + scorers) should be consistent across model comparisons. Individual runs can be named with `__weave={"display_name": "..."}` if needed.

### Part 6: Exception Tracking (15 mins)
**Key Points:**
- Automatic exception capture
- Full stack traces in UI
- Debug JSON parsing errors

**Activity:**
- Run the strict schema examples
- Show different error types
- Explore failed calls in UI

### Part 7: Cost & Performance (15 mins)
**Key Points:**
- Automatic token tracking
- Latency measurements
- Cost optimization strategies

**Show:**
- Token usage in traces
- Latency breakdown
- Fallback mechanism

### Part 8: Production Monitoring (20 mins)
**Key Points:**
- Scorers as guardrails vs monitors
- The `.call()` method for getting Call objects
- Async scoring patterns

**Demo:**
- Show ToxicityScorer blocking content
- Show ResponseQualityScorer tracking quality
- Demonstrate apply_scorer pattern

### Part 9: Debugging (15 mins)
**Key Points:**
- Failed calls highlighted in red
- Full error traces
- Input inspection

**Activity:**
- Run the problematic analyzer
- Find failures in UI
- Debug together

### Wrap-up (15 mins)
- Q&A session
- Show additional resources
- Mention built-in scorers
- Encourage experimentation

## 💡 Teaching Tips

### Keep It Interactive
- **Live Coding**: Type along with participants
- **UI Tours**: Frequently switch to Weave UI
- **Questions**: Pause for questions after each section

### Common Stumbling Blocks
1. **Async/Await**: 
   - In notebooks: Can use `await` directly or `asyncio.run()` with `nest_asyncio`
   - In scripts: Use `asyncio.run()`
   - Workshop code uses `asyncio.run()` for compatibility
2. **Type Hints**: Emphasize they improve Weave traces
3. **Dataset Format**: Show the expected structure clearly
4. **Model Quality**: Explain why basic model performs worse (intentional)

### Notebook vs Script Execution
- **Notebooks**: May need to replace `asyncio.run()` with `await`
- **Scripts**: Works as-is with `asyncio.run()`
- **Both**: Require `nest_asyncio` package

### Emphasize Practical Value
- "This helps you debug production issues"
- "See exactly where your money goes"
- "Catch regressions before deployment"
- "Block harmful content in real-time"

## 🎯 Key Weave Features to Highlight

1. **Automatic Tracing**
   - No manual instrumentation needed
   - Works with any Python function
   - Captures all inputs/outputs

2. **Rich UI**
   - Interactive trace explorer
   - Evaluation comparisons
   - Cost tracking
   - Exception details

3. **Evaluation Framework**
   - Flexible scorer system
   - Dataset versioning
   - Reproducible results
   - EvaluationLogger for custom workflows

4. **Production Ready**
   - Low overhead
   - Async support
   - Error handling
   - Scorer-based guardrails

## 📊 Suggested Demos

### Demo 1: The Power of Traces
Show a complex trace with multiple LLM calls, demonstrate:
- Time spent in each function
- Token usage per call
- Error propagation

### Demo 2: Evaluation Comparison
Open multiple evaluation runs and show:
- Score distributions
- Individual example inspection
- Model performance trends

### Demo 3: Exception Analysis
Show failed calls and demonstrate:
- Red highlighting for errors
- Full stack traces
- Input that caused failure

### Demo 4: Production Monitoring
Show scorer results and demonstrate:
- Toxic content blocking
- Quality score tracking
- Filtering by score values

## 🚨 Troubleshooting Guide

### "Can't see traces"
- Check Weave initialization
- Verify project name
- Ensure functions have `@weave.op`

### "Evaluation won't run"
- Check dataset format
- Verify scorer signatures
- Look for async/await issues

### "Asyncio errors"
- In notebooks: Use `await` or install `nest_asyncio`
- Check Python version (3.7+)
- Verify event loop not already running

### "API errors"
- Verify API keys
- Check rate limits
- Have backup keys ready

### "Scorer not working"
- Check `.call()` method usage
- Verify scorer inherits from Scorer
- Check parameter matching

## 📚 Additional Resources

Share these with participants:
- [Weave Documentation](https://weave-docs.wandb.ai/)
- [Built-in Scorers](https://weave-docs.wandb.ai/guides/evaluation/builtin_scorers)
- [Example Notebooks](https://github.com/wandb/weave/tree/main/examples)
- [Community Forum](https://community.wandb.ai/)

## 🎉 Making It Memorable

1. **Success Stories**: Share how teams use Weave
2. **Live Debugging**: Debug a real issue together
3. **Friendly Competition**: Who can create the best scorer?
4. **Encourage Sharing**: Have participants share their traces

## 📝 Post-Workshop

- Share recording (if applicable)
- Send follow-up resources
- Encourage participants to share their projects
- Collect feedback for improvement

Remember: The goal is for participants to leave excited about using Weave in their own projects! 🐝 