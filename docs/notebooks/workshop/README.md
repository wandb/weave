# 🐝 Weave Workshop: Build, Track, and Evaluate LLM Applications

<img src="http://wandb.me/logo-im-png" width="400" alt="Weights & Biases" />

Welcome to the Weave workshop! This hands-on session will teach you how to use Weave to develop, debug, and evaluate AI-powered applications.

## 🎯 What You'll Learn

- **🔍 Trace & Debug**: Track every LLM call, see inputs/outputs, and debug issues
- **📊 Evaluate**: Build rigorous evaluations with multiple scoring functions
- **🏃 Compare**: Run A/B tests and compare different approaches
- **📈 Monitor**: Track costs, latency, and performance metrics
- **🎯 Iterate**: Use data-driven insights to improve your application

## 🔑 Prerequisites

- Python 3.8+
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))
- Weights & Biases account ([Sign up free](https://wandb.ai/signup))
- Basic Python knowledge

## 🚀 Quick Start

### 1. Clone Workshop Materials
```bash
git clone <workshop-repo-url>
cd weave-workshop
```

### 2. Install Dependencies
```bash
pip install wandb weave openai pydantic nest_asyncio
```

### 3. Set API Keys
```bash
export WANDB_API_KEY='your-wandb-key'
export OPENAI_API_KEY='your-openai-key'
```

### 4. Run Setup Check
```bash
python workshop_quickstart.py
```

## 📚 Workshop Structure

The workshop is divided into 9 parts, each focusing on different Weave features:

1. **Tracing & Debugging** - Automatic function tracking with `@weave.op`
2. **Call Traces** - Debug complex pipelines with nested traces
3. **Evaluations** - Build comprehensive evaluation suites
4. **Model Comparison** - Compare different approaches systematically
5. **A/B Testing** - Run head-to-head model comparisons
6. **Cost Tracking** - Monitor token usage and latency
7. **Production Monitoring** - Track your app in production
8. **Error Debugging** - Find and fix issues quickly
9. **Advanced Features** - Metadata, custom attributes, and more

## 📁 Workshop Files

- **`weave_features_workshop.py`** - Main workshop notebook
- **`workshop_evaluation_examples.py`** - Advanced evaluation patterns
- **`workshop_quickstart.py`** - Environment setup checker
- **`README.md`** - This file
- **`instructor_guide.md`** - Guide for instructors

### 📓 Converting to Jupyter Notebooks

The workshop files are provided as Python scripts for better version control and compatibility. 
If you prefer Jupyter notebooks, you can convert them:

```bash
# Install jupytext if needed
pip install jupytext

# Convert to notebooks
jupytext --to notebook weave_features_workshop.py workshop_evaluation_examples.py

# Or use the provided script
./convert_to_notebooks.sh

# Or use make
make notebooks
```

## 🛠️ Key Concepts

### @weave.op Decorator
```python
@weave.op
def my_function(input: str) -> str:
    # Your function is automatically traced!
    return process(input)
```

### Models
```python
class MyModel(weave.Model):
    # Define parameters
    temperature: float = 0.7
    
    @weave.op
    def predict(self, input: str) -> str:
        # Model logic here
        return output
```

### Evaluations
```python
evaluation = weave.Evaluation(
    dataset=my_dataset,
    scorers=[my_scorer],
)
await evaluation.evaluate(my_model)
```

## 💡 Workshop Tips

1. **Follow Along**: Run each code cell and check the Weave UI
2. **Experiment**: Try modifying the examples
3. **Check the UI**: The Weave dashboard shows rich visualizations
4. **Ask Questions**: The instructors are here to help!

## 🔍 Exploring the Weave UI

After running examples, visit [wandb.ai](https://wandb.ai) to:

- View call traces with inputs and outputs
- See evaluation results and comparisons
- Analyze performance metrics
- Debug errors with full stack traces
- Compare different model versions

## 🐛 Troubleshooting

### API Key Issues
```bash
# Check if keys are set
echo $WANDB_API_KEY
echo $OPENAI_API_KEY
```

### Import Errors
```bash
# Reinstall dependencies
pip install --upgrade wandb weave openai pydantic nest_asyncio
```

### Async/Await in Notebooks
If you're running in a Jupyter notebook and see asyncio errors:
- The workshop code uses `asyncio.run()` for compatibility
- In Jupyter, you can replace `asyncio.run(...)` with `await ...`
- Or use the provided code as-is with `nest_asyncio` installed

### Weave Connection Issues
```python
# Reinitialize Weave
import weave
weave.init("your-project-name")
```

## 🎓 After the Workshop

- **Documentation**: [weave-docs.wandb.ai](https://weave-docs.wandb.ai/)
- **Examples**: Check the [Weave cookbook](https://github.com/wandb/weave/tree/main/examples)
- **Community**: Join the [W&B Community](https://wandb.ai/community)
- **Support**: Get help in [W&B Forums](https://community.wandb.ai/)

## 🚀 Next Steps

1. **Build**: Create your own LLM application with Weave
2. **Evaluate**: Design comprehensive evaluation suites
3. **Monitor**: Deploy with production monitoring
4. **Share**: Show your work to the community!

Happy building with Weave! 🐝 