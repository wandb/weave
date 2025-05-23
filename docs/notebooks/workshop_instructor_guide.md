# Prompt Engineering Workshop with Weave - Instructor Guide

## Workshop Overview
**Duration**: 2-3 hours  
**Level**: Beginner to Intermediate  
**Prerequisites**: Basic Python knowledge, OpenAI API key

## Learning Objectives
By the end of this workshop, participants will:
1. Understand core prompt engineering techniques
2. Know how to iterate and improve prompts systematically
3. Be able to use Weave to track and compare LLM experiments
4. Build evaluation datasets and scoring functions
5. Apply advanced techniques like few-shot learning and chain-of-thought

## Workshop Structure

### Part 1: Introduction (15 mins)
- Welcome and introductions
- Overview of prompt engineering importance
- Introduction to Weave and its benefits
- Quick demo of the Weave dashboard

### Part 2: Basic Extraction (30 mins)
**Key Concepts**:
- Structured output from unstructured text
- Using response_format for JSON
- The @weave.op decorator

**Teaching Points**:
- Start with the simplest possible prompt
- Show how Weave automatically tracks the function calls
- Demonstrate the Weave UI showing inputs/outputs

**Common Issues**:
- JSON parsing errors → explain response_format parameter
- Missing fields → importance of clear instructions

### Part 3: Prompt Iteration (30 mins)
**Key Concepts**:
- Iterative improvement
- Being specific in instructions
- Temperature control

**Activities**:
- Have students modify v2 to add their own improvements
- Compare results in Weave dashboard
- Discuss what changes led to improvements

### Part 4: Few-Shot Learning (30 mins)
**Key Concepts**:
- Examples guide model behavior
- Consistency through demonstration
- When to use few-shot vs zero-shot

**Hands-on Exercise**:
- Students create their own few-shot examples
- Test with edge cases
- Measure improvement over zero-shot

### Part 5: Evaluation (45 mins)
**Key Concepts**:
- Building test datasets
- Scoring functions
- Systematic comparison

**Interactive Section**:
- Students build their own test cases
- Design custom scoring metrics
- Run evaluations and analyze results

### Part 6: Advanced Techniques (30 mins)
**Techniques to Cover**:
1. Chain of Thought (CoT)
2. Role-based prompting
3. Self-consistency
4. Constitutional AI principles

**Group Activity**:
- Split into teams
- Each team implements one technique
- Present results to the group

### Part 7: Exercises & Challenges (30 mins)
**Exercise Options**:
1. **Edge Case Challenge**: Handle emails with missing information
2. **Multi-field Extension**: Add urgency, sentiment, category
3. **Language Challenge**: Support non-English emails
4. **Production Ready**: Add error handling and validation

## Key Weave Features to Highlight

1. **Automatic Tracing**
   - Show how @weave.op captures all function calls
   - Demonstrate the call tree in the UI

2. **Version Comparison**
   - Compare different prompt versions side-by-side
   - Show performance metrics (latency, token usage)

3. **Dataset Management**
   - Create and version datasets
   - Link evaluations to specific datasets

4. **Evaluation Tracking**
   - Show how scoring functions are tracked
   - Demonstrate aggregate metrics

5. **Error Handling**
   - Show how Weave captures errors
   - Use for debugging prompt issues

## Common Questions & Answers

**Q: Why use Weave instead of just print statements?**
A: Weave provides persistent tracking, comparison tools, and team collaboration features. It's like git for your LLM experiments.

**Q: How do I handle rate limits?**
A: Add retry logic with exponential backoff. Weave will track all attempts.

**Q: What's the best prompt engineering technique?**
A: It depends on your use case. That's why systematic evaluation is crucial.

**Q: Can I use this with other LLMs?**
A: Yes! Weave works with any LLM. Just wrap your calls with @weave.op.

## Tips for Success

1. **Live Coding**: Code along with students, make mistakes intentionally
2. **Real Examples**: Use actual customer emails if possible
3. **Encourage Experimentation**: No "wrong" prompts, only learning opportunities
4. **Share the Dashboard**: Project the Weave UI frequently
5. **Peer Learning**: Have students share their prompts and results

## Additional Resources
- [Weave Documentation](https://wandb.ai/docs/weave)
- [OpenAI Prompt Engineering Guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [Anthropic's Prompt Engineering Tutorial](https://docs.anthropic.com/claude/docs/prompt-engineering)

## Workshop Checklist
- [ ] All participants have OpenAI API keys
- [ ] Weave accounts created
- [ ] Jupyter environments working
- [ ] Sample notebook distributed
- [ ] Backup API key available
- [ ] Screen sharing tested
- [ ] Weave dashboard accessible

## Extension Ideas
- Building a complete customer support bot
- A/B testing different prompts in production
- Cost optimization strategies
- Building prompt templates library
- Integration with existing workflows 