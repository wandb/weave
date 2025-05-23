# 🐝 Weave Workshop - Instructor Guide

## Workshop Overview
**Duration**: 2-3 hours  
**Focus**: Hands-on experience with Weave features  
**Goal**: Participants leave knowing how to use Weave to build, debug, and evaluate LLM applications

## 🎯 Learning Objectives

By the end of this workshop, participants will be able to:
1. Use `@weave.op` to trace function calls
2. Debug LLM applications using Weave's UI
3. Build and run evaluations
4. Compare models systematically
5. Monitor applications in production
6. Use Weave for cost and performance tracking

## 📋 Pre-Workshop Checklist

- [ ] Participants have W&B accounts
- [ ] OpenAI API keys ready (have backup keys)
- [ ] Workshop notebooks downloaded
- [ ] Weave UI accessible
- [ ] Screen sharing setup tested
- [ ] Example traces pre-generated (optional)

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
Show how to click through individual examples in the eval results

### Part 4: Model Comparison (20 mins)
**Key Points:**
- Models encapsulate parameters
- Easy A/B testing
- Side-by-side comparisons in UI

**Demo:**
- Show the three model variants
- Run evaluations on each
- Use Weave's comparison view

### Part 5: A/B Testing (15 mins)
**Key Points:**
- Head-to-head comparisons
- Statistical insights
- Decision making with data

**Interactive:**
- Let participants suggest new model variants
- Run live A/B test
- Discuss results

### Part 6: Cost & Performance (15 mins)
**Key Points:**
- Automatic token tracking
- Latency measurements
- Cost optimization strategies

**Show:**
- Token usage in traces
- Latency breakdown
- Fallback mechanism

### Part 7: Production Monitoring (15 mins)
**Key Points:**
- Production-ready patterns
- Error tracking
- Alerting on issues

**Discuss:**
- Request ID tracking
- Error handling patterns
- Monitoring dashboards

### Part 8: Debugging (15 mins)
**Key Points:**
- Failed calls highlighted in red
- Full error traces
- Input inspection

**Activity:**
- Run the problematic analyzer
- Find failures in UI
- Debug together

### Part 9: Advanced Features (10 mins)
**Quick Overview:**
- Custom metadata
- Tagging and filtering
- Export capabilities

### Wrap-up (15 mins)
- Q&A session
- Show additional resources
- Encourage experimentation

## 💡 Teaching Tips

### Keep It Interactive
- **Live Coding**: Type along with participants
- **UI Tours**: Frequently switch to Weave UI
- **Questions**: Pause for questions after each section

### Common Stumbling Blocks
1. **Async/Await**: Some may not be familiar - explain briefly
2. **Type Hints**: Emphasize they improve Weave traces
3. **Dataset Format**: Show the expected structure clearly

### Emphasize Practical Value
- "This helps you debug production issues"
- "See exactly where your money goes"
- "Catch regressions before deployment"

## 🎯 Key Weave Features to Highlight

1. **Automatic Tracing**
   - No manual instrumentation needed
   - Works with any Python function
   - Captures all inputs/outputs

2. **Rich UI**
   - Interactive trace explorer
   - Evaluation comparisons
   - Cost tracking

3. **Evaluation Framework**
   - Flexible scorer system
   - Dataset versioning
   - Reproducible results

4. **Production Ready**
   - Low overhead
   - Async support
   - Error handling

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

### Demo 3: Cost Analysis
Filter traces by date and show:
- Total token usage
- Cost per model
- Optimization opportunities

## 🚨 Troubleshooting Guide

### "Can't see traces"
- Check Weave initialization
- Verify project name
- Ensure functions have `@weave.op`

### "Evaluation won't run"
- Check dataset format
- Verify scorer signatures
- Look for async/await issues

### "API errors"
- Verify API keys
- Check rate limits
- Have backup keys ready

## 📚 Additional Resources

Share these with participants:
- [Weave Documentation](https://weave-docs.wandb.ai/)
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