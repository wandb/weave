# 🚀 Prompt Engineering Workshop with Weave

Welcome to the hands-on prompt engineering workshop! In this session, you'll learn how to build better LLM applications using systematic prompt engineering techniques and Weave's powerful tracking capabilities.

## 🎯 What You'll Learn

- **Prompt Engineering Fundamentals**: Extract structured data from unstructured text
- **Iterative Improvement**: Use data-driven approaches to enhance prompts
- **Advanced Techniques**: Master few-shot learning, chain-of-thought, and role-based prompting
- **Evaluation & Testing**: Build robust evaluation frameworks
- **Weave Mastery**: Track, compare, and optimize your LLM experiments

## 📋 Prerequisites

- Basic Python knowledge
- OpenAI API key (get one at https://platform.openai.com)
- Laptop with Python 3.8+ installed
- Enthusiasm for learning!

## 🛠️ Setup Instructions

### 1. Clone or Download Workshop Materials
```bash
git clone <workshop-repo-url>
cd prompt-engineering-workshop
```

### 2. Create Virtual Environment (Recommended)
```bash
python -m venv workshop_env
source workshop_env/bin/activate  # On Windows: workshop_env\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install weave openai pydantic jupyter
```

### 4. Set Your OpenAI API Key
```bash
export OPENAI_API_KEY='your-api-key-here'  # On Windows: set OPENAI_API_KEY=your-api-key-here
```

### 5. Verify Setup
```bash
python workshop_quickstart.py
```

You should see all green checkmarks! ✅

### 6. Create Weave Account
Visit https://wandb.ai/signup and create a free account to use Weave.

## 📚 Workshop Files

- **`prompt_engineering_workshop_complete.ipynb`** - Main workshop notebook with all exercises
- **`workshop_quickstart.py`** - Setup verification script
- **`workshop_instructor_guide.md`** - Instructor reference (if you're teaching)
- **`workshop_solutions.ipynb`** - Solutions to exercises (no peeking! 😉)

## 🚀 Quick Start

1. Open Jupyter:
   ```bash
   jupyter notebook prompt_engineering_workshop_complete.ipynb
   ```

2. Follow along with the instructor or work at your own pace

3. Visit your Weave dashboard at https://wandb.ai/home to see your experiments

## 💡 Workshop Structure

### Part 1: Basic Extraction (30 mins)
Start with simple prompts to extract customer information from support emails.

### Part 2: Prompt Iteration (30 mins)
Learn how to systematically improve your prompts using Weave tracking.

### Part 3: Few-Shot Learning (30 mins)
Add examples to dramatically improve extraction accuracy.

### Part 4: Evaluation (45 mins)
Build datasets and scoring functions to measure success.

### Part 5: Advanced Techniques (30 mins)
Explore chain-of-thought, role-based prompting, and more.

### Part 6: Hands-On Exercises (30 mins)
Apply what you've learned to real-world challenges.

## 🎯 Use Case: Customer Support Triage

Throughout the workshop, we'll build a system that extracts key information from customer support emails:
- Customer name
- Product model
- Issue description
- (Advanced) Urgency level, sentiment, and category

## 🛟 Troubleshooting

### "Module not found" errors
Make sure you've activated your virtual environment and installed all dependencies.

### OpenAI API errors
- Check your API key is set correctly
- Ensure you have credits in your OpenAI account
- Watch for rate limits (we use GPT-3.5-turbo which has generous limits)

### Weave connection issues
- Make sure you're logged in at https://wandb.ai
- Check your internet connection
- Try running `weave.init("test_project")` in a Python shell

### JSON parsing errors
The workshop uses `response_format={"type": "json_object"}` to ensure valid JSON. If you still get errors, check your prompt formatting.

## 📝 Tips for Success

1. **Experiment Freely**: There's no "wrong" prompt - try different approaches!
2. **Use Weave Dashboard**: Regularly check your experiments at wandb.ai
3. **Ask Questions**: Your instructor is here to help
4. **Take Notes**: Document what works and what doesn't
5. **Share Insights**: Learn from other participants' approaches

## 🔗 Additional Resources

- [Weave Documentation](https://wandb.ai/docs/weave)
- [OpenAI Cookbook](https://cookbook.openai.com/)
- [Prompt Engineering Guide](https://www.promptingguide.ai/)
- [LangChain Prompt Templates](https://python.langchain.com/docs/modules/model_io/prompts/)

## 🤝 Getting Help

During the workshop:
- Raise your hand for in-person help
- Use the workshop Slack/Discord channel
- Check with your neighbor - peer learning is encouraged!

After the workshop:
- Join the Weave community at https://wandb.ai/community
- Post questions on the workshop forum
- Reach out to your instructor

## 🎉 Ready to Start?

Run the quickstart script to verify everything is working:
```bash
python workshop_quickstart.py
```

Then open the workshop notebook and let's build something amazing!

```bash
jupyter notebook prompt_engineering_workshop_complete.ipynb
```

Happy prompting! 🚀 