# 🎤 Weave Workshop Talk Track

## 🎬 Pre-Workshop (5 mins before start)
**[Slides showing, chat open, music playing softly]**

"Welcome everyone! We'll be starting in just a few minutes. While we wait, please run the setup check script if you haven't already. Drop a 👍 in chat when you see all green checkmarks!"

"If you're having any setup issues, now's a great time to let us know in chat."

---

## 🚀 Introduction (10 mins)

### Opening Hook (2 mins)
"Good [morning/afternoon] everyone! Quick show of hands - who here has ever spent hours debugging an LLM application, trying to figure out why it gave a weird response? 

[Pause for responses]

Yeah, I see those knowing nods! Well, today you're going to learn how to make that debugging process 10x easier. Welcome to the Weave workshop!"

### What is Weave? (3 mins)
"So what exactly is Weave? Think of it as your AI application's best friend. It's like having X-ray vision into your LLM calls.

[Show a complex trace in the UI]

Look at this - every input, every output, every token, every millisecond - all captured automatically. No more print statements, no more guessing. 

But here's where it gets really powerful - Weave doesn't just help you debug. It helps you systematically improve your AI applications through rigorous evaluation."

### Workshop Overview (3 mins)
"Today we're going to build a customer support email analyzer together. Why? Because it's a real problem many of you face, and it perfectly demonstrates Weave's capabilities.

By the end of this workshop, you'll know how to:
- Trace every LLM call automatically
- Build comprehensive evaluations
- Compare models scientifically
- Track and debug exceptions
- Monitor production applications with guardrails
- And debug issues in seconds instead of hours

Let's make sure everyone's ready..."

### Environment Check (2 mins)
"Everyone, please run:
```bash
python workshop_quickstart.py
```

Drop a 🎉 in chat when you see 'All checks passed!' 

[Wait for responses]

Perfect! If anyone's still having issues, our TAs will help you out."

---

## 📚 Part 1: Tracing & Debugging (20 mins)

### Introduction to @weave.op (5 mins)
"Let's start with the magic decorator that makes everything possible: `@weave.op`

[Show code]

See this simple decorator? Add it to ANY Python function, and boom - that function is now traced. Every input, every output, automatically logged.

Let me show you something cool. I'm going to run this customer email analyzer..."

[Run the analyze_customer_email function]

### Live Demo (5 mins)
"Watch this - I'll run the function, and let's see what happens in the Weave UI...

[Switch to Weave UI]

Look at this! We can see:
- The exact email input
- The structured output from GPT-3.5
- How long it took (about 1.2 seconds)
- Even the exact model used

Click on the trace... and we can see the full OpenAI request and response. This is incredibly powerful for debugging."

### Why This Matters (3 mins)
"Think about your last LLM project. How did you debug it? Console logs? Print statements? 

With Weave, you get a full history of every call. Customer complaining about a bad response from last week? No problem - find that exact trace, see what went wrong.

And the best part? Zero performance overhead in production."

### Hands-On (7 mins)
"Your turn! Modify the email analyzer:
1. Change the test email to something from your domain
2. Add a new field to extract (maybe 'priority' or 'department')
3. Run it and explore the trace

I'll give you 5 minutes. Drop questions in chat if you get stuck!"

[Timer: 5 minutes]

"Alright, who wants to share what they found in their trace? Anyone discover something interesting?"

---

## 🔍 Part 2: Call Traces (15 mins)

### Nested Traces Concept (3 mins)
"Now let's level up. Real applications aren't just one function - they're pipelines. Weave handles this beautifully.

[Show the process_support_ticket code]

See how we're composing multiple functions? Each with @weave.op? This creates a trace tree."

### Live Pipeline Demo (5 mins)
"Watch what happens when I run this pipeline...

[Run process_support_ticket]

[Switch to Weave UI]

This is gorgeous! Look at the trace tree:
- Parent: process_support_ticket (total: 1.5s)
  - Child: preprocess_email (0.001s)
  - Child: analyze_customer_email (1.2s) 
  - Child: classify_urgency (0.002s)

You can see EXACTLY where time is spent. Is the LLM call slow? Is preprocessing taking too long? Now you know!"

### Debugging Power (3 mins)
"Here's a real scenario: A customer says your app classified their urgent email as low priority. 

In the old world: Good luck reproducing that!

With Weave: Find their trace, click through the pipeline, see exactly what the classify_urgency function received and why it made that decision."

### Your Turn (4 mins)
"Challenge time! Add your own step to the pipeline:
- Maybe a 'suggest_response' function?
- Or 'detect_language'?
- Or 'extract_account_number'?

Remember to add @weave.op! Give it a try."

[Timer: 3 minutes]

---

## 📊 Part 3: Building Evaluations (30 mins)

### Why Evaluate? (5 mins)
"Alright, this is where Weave gets REALLY powerful. How do you know if your prompt changes actually improved things? How do you catch regressions before production?

The answer: Systematic evaluation.

[Show evaluation dataset]

Look at this - we've created a more challenging test dataset with tricky names, product versions, and edge cases. This is your safety net."

### Understanding Scorers (5 mins)
"Scorers are functions that measure how well your model performs. Let's look at three types:

1. **Exact Match** - Did it extract the name correctly?
2. **Semantic** - Is the sentiment analysis right?
3. **Quality** - Overall extraction quality

[Show scorer code]

Notice how each scorer returns a score between 0 and 1? This lets us aggregate and compare."

### Running First Evaluation (10 mins)
"Let's run our first evaluation together...

[Run the evaluation]

This is running our analyzer on each test example and applying all three scorers. 

[Switch to Weave UI after completion]

😍 Look at this evaluation dashboard! 
- Overall scores for each metric
- Drill down into individual examples
- See exactly where the model succeeded or failed

Click on a failed example... see exactly what went wrong. Notice how it struggles with complex names and product versions? This is how you improve systematically!"

### Interpreting Results (5 mins)
"Let's analyze these results together:
- Name accuracy: Lower than expected - Why? [Click through to see]
- Sentiment accuracy: Pretty good!
- Extraction quality: Room for improvement

What patterns do you notice? The model struggles with names in signatures and product version numbers."

### Group Exercise (5 mins)
"Let's add a new scorer together. What about checking if the product version was extracted correctly?

[Code along with participants]

See how easy that was? You can create scorers for ANY criteria that matters to your application."

---

## 📝 Part 3b: EvaluationLogger (10 mins)

### Flexible Evaluation Logging (3 mins)
"Sometimes you need more control over your evaluation process. Maybe you're processing data incrementally, or you want custom logging logic. That's where EvaluationLogger comes in.

[Show EvaluationLogger code]

Key difference from standard Evaluation - there are no Model or Dataset objects here. So the identification is CRUCIAL. Look at this:
- Simple strings work: 'email_analyzer_gpt35'
- But dictionaries are better! You can track version, parameters, anything
- This metadata helps you filter and compare evaluations later

See how we can log predictions one by one, add multiple scores per prediction, and even handle errors gracefully?"

### Live Demo (5 mins)
"Watch this - we're logging each prediction individually...

[Run the EvaluationLogger example]

Notice how we're using rich metadata:
- Model: version, LLM type, temperature, prompt version
- Dataset: version, size, source
- This makes it super easy to filter in the UI later!

We can:
- Process examples one at a time
- Add custom business logic scores
- Handle errors without stopping the whole evaluation
- Add summary statistics at the end

This is perfect for production scenarios where you're evaluating continuously!"

### When to Use (2 mins)
"Use EvaluationLogger when:
- You're processing streaming data
- You need custom scoring logic
- You want to handle errors gracefully
- You're building custom evaluation pipelines

It's more flexible than the standard Evaluation, but requires more code."

---

## 🏆 Part 4: Model Comparison (20 mins)

### The Power of A/B Testing (5 mins)
"Here's the million-dollar question: Is GPT-4 really better than GPT-3.5 for YOUR use case? Is temperature 0 better than 0.9? 

Without Weave: You're guessing.
With Weave: You have data.

Let me show you how to compare models scientifically..."

### Creating Model Variants (5 mins)
"Look at how we define model variants:

[Show EmailAnalyzerModel class]

Each model is a configuration - different prompts, temperatures, even different LLMs. Notice how we've made the basic model intentionally worse with a simple prompt and high temperature?"

### Running Comparisons (5 mins)
"Watch this - we'll compare three variants:

[Run model comparison]

Important point here - notice we create ONE evaluation object and use it for all models. Why? Because:
- The evaluation definition (dataset + scorers) is the same
- Each run automatically gets a unique ID
- This lets everyone in the workshop compare results!

We can optionally name individual runs with display_name, but the evaluation itself stays consistent."

### Analyzing Results (5 mins)
"[Open Weave UI comparison view]

🤯 This is beautiful! Side-by-side comparison:
- Basic model: Lower scores as expected
- Detailed model: Best performance with GPT-4  
- Balanced model: Good middle ground

But here's the key insight - look at the breakdown by metric. The detailed model is best overall but costs more. The balanced model might be your sweet spot for production!"

---

## 🐞 Part 6: Exception Tracking (15 mins)

### When Things Go Wrong (3 mins)
"Let's talk about something that happens in every production system - exceptions. How quickly can you figure out what went wrong?

[Show DetailedCustomerEmail schema]

Look at this stricter schema - it requires more fields, making failures more likely. This is actually good for learning!"

### Live Exception Demo (7 mins)
"Watch what happens when we feed it problematic inputs...

[Run exception tracking examples]

Look at the different types of failures:
- Too short emails fail parsing
- Missing fields cause validation errors
- Invalid JSON crashes everything

[Switch to Weave UI]

In the Weave UI, failed calls are highlighted in red. Click on one... you see the FULL stack trace, the exact input that caused it, and when it happened. This is gold for debugging!"

### JSON Parsing Errors (3 mins)
"Here's a common scenario - expecting JSON responses:

[Run JSON parsing examples]

See how Weave captures different error types? JSONDecodeError vs KeyError - each tells you exactly what went wrong."

### Your Turn (2 mins)
"Try to break the analyzer! Feed it weird inputs and see what exceptions you can trigger. Check the Weave UI to see how they're tracked."

---

## 💰 Part 7: Cost & Performance (15 mins)

### The Hidden Costs (3 mins)
"Let's talk about something that matters to your boss - money. LLM calls aren't free, and they add up FAST.

Weave automatically tracks:
- Token usage (input and output)
- Latency for each call
- Which models you're using

This isn't just nice to have - it's essential for production."

### Fallback Patterns (5 mins)
"Here's a production pattern everyone should use - fallbacks:

[Show analyze_with_fallback code]

If GPT-4 fails or is too slow, automatically fall back to GPT-3.5. But here's the key - Weave tracks both attempts!"

[Run the fallback example]

### Cost Analysis (4 mins)
"[In Weave UI]

Look at this cost tracking:
- GPT-4 call: More expensive but more accurate
- GPT-3.5 fallback: Cheaper but still works
- You can see exactly when fallbacks happen

Now multiply that by 100,000 calls per day... you see why this matters?"

### Optimization Exercise (3 mins)
"Quick exercise: If you had to reduce costs by 50%, what would you do? Think about:
- Model selection
- Prompt length optimization
- Caching strategies

Share your ideas in chat!"

---

## 🏭 Part 8: Production Monitoring with Scorers (20 mins)

### Guardrails vs Monitors (5 mins)
"Production isn't just about handling requests - it's about ensuring quality and safety. Weave's scorer system gives you both guardrails and monitors.

**Guardrails**: Block bad content before users see it
**Monitors**: Track quality over time

The beauty? They use the same scorer interface!"

### Building Production Scorers (5 mins)
"Look at our custom scorers:

[Show ToxicityScorer and ResponseQualityScorer]

The ToxicityScorer acts as a guardrail - it can block content.
The ResponseQualityScorer monitors extraction quality - it helps you improve.

Notice how scorers can access both the output AND the original input?"

### Live Production Demo (7 mins)
"Let's see this in action...

[Run production monitoring example]

Watch what happens:
1. Email gets processed
2. We get the Call object using .call()
3. Scorers run asynchronously
4. Toxic content gets flagged
5. Quality issues are logged

[Switch to Weave UI]

In the UI, you can see scorer results attached to each call. Filter by score values, find problematic requests, analyze patterns!"

### Best Practices (3 mins)
"Production tips:
1. Initialize scorers once (outside your handler)
2. Use async scoring for better performance
3. Set appropriate thresholds
4. Sample monitoring to reduce load
5. Always handle scorer failures gracefully"

---

## 🐛 Part 9: Debugging Failed Calls (15 mins)

### When Things Go Wrong (3 mins)
"Let's be honest - things WILL go wrong in production. The question is: how quickly can you fix them?

[Show problematic_analyzer code]

This analyzer has intentional bugs. Let's see how Weave helps us debug..."

### Live Debugging Session (7 mins)
"[Run problematic examples]

Look at the Weave UI - failed calls are highlighted in red. Click on one...

We can see:
- The exact input that caused the failure
- The full stack trace
- The timestamp
- Any custom metadata

This transforms debugging from hours to minutes!"

### Common Failure Patterns (3 mins)
"From experience, here are the most common LLM failures:
1. Timeout/rate limits
2. Invalid structured output
3. Token limits exceeded
4. Unexpected input formats

Weave helps you catch all of these patterns."

### Group Debugging (2 mins)
"I'm going to cause an error intentionally. Work with your neighbor to:
1. Find the failed trace
2. Identify the root cause
3. Suggest a fix

Go!"

---

## 🎉 Wrap-Up (15 mins)

### Key Takeaways (5 mins)
"Let's recap what you've learned:

✅ **Tracing** - Never guess what your AI is doing
✅ **Evaluation** - Measure to improve systematically
✅ **Comparison** - Make data-driven decisions
✅ **Exception Tracking** - Debug failures instantly
✅ **Monitoring** - Production-grade observability with scorers
✅ **Cost Tracking** - Know where your money goes

You now have superpowers for building AI applications!"

### Your Next Steps (3 mins)
"Here's what I want you to do next:

1. **This week**: Add Weave to one existing project
2. **Next week**: Create an evaluation suite
3. **This month**: Run your first model comparison
4. **Explore**: Try the built-in scorers (HallucinationFreeScorer, SummarizationScorer)
5. **Share**: Tweet your traces! Tag @weights_biases

Remember - the goal isn't just to build AI apps, it's to build GREAT AI apps."

### Resources & Community (2 mins)
"You're not alone in this journey:

📚 **Docs**: weave-docs.wandb.ai
💬 **Community**: community.wandb.ai
🎥 **YouTube**: More tutorials coming
📧 **Email**: weave-support@wandb.com

And don't forget - your instructor guide and workshop materials are always available!"

### Q&A (5 mins)
"We have a few minutes for questions. What would you like to know more about? 

[Address questions]

Remember - there are no stupid questions, only untraced LLM calls! 😄"

### Closing (30 seconds)
"Thank you all for joining today! You came in wondering how to debug LLM apps, and you're leaving with a complete toolkit for building, evaluating, and monitoring AI applications.

Go forth and build amazing things! And remember - with Weave, you're never debugging in the dark again.

See you in the Weave community! 🐝"

---

## 📝 Post-Workshop Message

"Thanks for attending! Here's your homework:
1. ⭐ Star the Weave repo
2. 📤 Share what you built today
3. 🎯 Apply Weave to your current project
4. 💬 Join our Discord for help

Workshop materials: [link]
Recording: [available soon]

Happy building! 🚀" 