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
- Monitor production applications
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
- The structured output from GPT-4
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

Look at this - we've created a test dataset with examples and expected outputs. This is your safety net."

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

Click on a failed example... see exactly what went wrong. This is how you improve systematically!"

### Interpreting Results (5 mins)
"Let's analyze these results together:
- Name accuracy: 67% - Why? [Click through to see]
- Sentiment accuracy: 100% - Great!
- Extraction quality: 78% - Room for improvement

What patterns do you notice? Where is our model struggling?"

### Group Exercise (5 mins)
"Let's add a new scorer together. What about checking if the product name is spelled correctly? Or if the issue description is concise?

[Code along with participants]

See how easy that was? You can create scorers for ANY criteria that matters to your application."

---

## 🏆 Part 4: Model Comparison (20 mins)

### The Power of A/B Testing (5 mins)
"Here's the million-dollar question: Is GPT-4 really better than GPT-3.5 for YOUR use case? Is temperature 0 better than 0.7? 

Without Weave: You're guessing.
With Weave: You have data.

Let me show you how to compare models scientifically..."

### Creating Model Variants (5 mins)
"Look at how we define model variants:

[Show EmailAnalyzerModel class]

Each model is a configuration - different prompts, temperatures, even different LLMs. This is proper experimentation!"

### Running Comparisons (5 mins)
"Watch this - we'll compare three variants:

[Run model comparison]

While this runs, notice we're using THE SAME evaluation dataset. This is crucial for fair comparison."

### Analyzing Results (5 mins)
"[Open Weave UI comparison view]

🤯 This is beautiful! Side-by-side comparison:
- Basic model: 72% average
- Detailed model: 89% average  
- Empathetic model: 81% average

But here's the key insight - look at the breakdown by metric. The empathetic model is best at sentiment but worse at name extraction. 

This is how you make informed decisions!"

---

## 💰 Part 6: Cost & Performance (15 mins)

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
- GPT-4 call: ~$0.003 
- GPT-3.5 fallback: ~$0.0004
- That's 7.5x difference!

Now multiply that by 100,000 calls per day... you see why this matters?"

### Optimization Exercise (3 mins)
"Quick exercise: If you had to reduce costs by 50%, what would you do? Think about:
- Model selection
- Prompt length
- Caching strategies

Share your ideas in chat!"

---

## 🏭 Part 7: Production Monitoring (15 mins)

### Production Realities (3 mins)
"Development is one thing, but production is where things get real. You need:
- Error tracking
- Performance monitoring  
- Alerting on anomalies
- Request tracing

Weave gives you all of this out of the box."

### Production Patterns (5 mins)
"Look at this production-ready handler:

[Show production_email_handler code]

Key features:
- Request ID tracking
- Error handling
- Performance metrics
- Priority alerting

This is how you sleep well at night!"

### Monitoring Demo (4 mins)
"Let's simulate production traffic...

[Run production simulation]

In Weave UI, you can:
- Filter by time range
- Search by request ID
- Set up alerts for high-urgency tickets
- Track error rates

This is enterprise-grade monitoring for AI applications."

### Best Practices (3 mins)
"Production tips from the trenches:
1. Always use request IDs
2. Log business metrics, not just technical ones
3. Set up alerts for anomalies
4. Review traces weekly with your team"

---

## 🐛 Part 8: Debugging Failed Calls (15 mins)

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
2. Invalid JSON responses
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

## 🎯 Part 9: Advanced Features (10 mins)

### Custom Metadata (3 mins)
"Let's talk about some power features. First - custom metadata:

[Show analyze_with_metadata code]

You can attach ANY metadata to traces:
- User IDs
- Feature flags
- A/B test variants
- Business context

This makes analysis incredibly powerful."

### Quick Tips (4 mins)
"Lightning round of pro tips:

1. **Use tags** - Tag traces with environment, version, customer tier
2. **Create dashboards** - Save your favorite queries  
3. **Export data** - Get CSVs for deeper analysis
4. **Integrate with alerts** - Connect to PagerDuty, Slack
5. **Use in CI/CD** - Run evaluations in your pipeline"

### The Future (3 mins)
"Where is this going? Imagine:
- Automatic prompt optimization based on evaluations
- Anomaly detection on model behavior  
- Cost optimization recommendations
- Team collaboration on debugging

The future of AI development is observable, measurable, and improving!"

---

## 🎉 Wrap-Up (15 mins)

### Key Takeaways (5 mins)
"Let's recap what you've learned:

✅ **Tracing** - Never guess what your AI is doing
✅ **Evaluation** - Measure to improve
✅ **Comparison** - Make data-driven decisions
✅ **Monitoring** - Production-grade observability
✅ **Debugging** - From hours to minutes

You now have superpowers for building AI applications!"

### Your Next Steps (3 mins)
"Here's what I want you to do next:

1. **This week**: Add Weave to one existing project
2. **Next week**: Create an evaluation suite
3. **This month**: Run your first model comparison
4. **Share**: Tweet your traces! Tag @weights_biases

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