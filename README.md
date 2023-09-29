![Weave Logo](./docs/assets/logo_horizontal.svg)

### **Weave** - Interactive Data Exploration Toolkit by [Weights & Biases](https://wandb.ai/)

---

Hello 👋 and welcome to Weave!

Weave, developed by the team at Weights and Biases, is a new open-source toolkit designed for performant, interactive data exploration.
Our mission is to equip Machine Learning practitioners with the best tools to turn data into insights quickly and easily.

Whether you are a seasoned data scientist, an aspiring ML practitioner, or just a tech enthusiast eager to play with data, Weave is for you.

### 🔆 [Join the W&B Prompts Feedback Sprint - Sep 29th - Oct 22nd](examples/prompts/FEEDBACK_SPRINT.md) 🔆

**Try W&B Prompts, share your thoughts, win swag!**

The W&B engineering team want your feedback on how our new LLM tool, LLM Monitoring, can be tailored to your specific use cases. The programme closes Sunday, October 22nd 2023, **[click here to participate](examples/prompts/FEEDBACK_SPRINT.md)** and be in for a chance to win some W&B swag.

## Getting Started with Weave

[Run in a Google Colab ->](https://colab.research.google.com/drive/1TwlhvvoWIHKDtRUu6eW0NMRq0GzGZ9oX)
[Run in a Jupyter notebook ->](./examples/get_started.ipynb)

Install via `pip install weave`, `import weave` in your notebook, and explore your data  with one line of code!

**1. View a dataframe**

```python
import weave
from sklearn.datasets import load_iris

# use any existing dataframe, here we load the iris data and visualize the labels
iris = load_iris(as_frame=True)
df = iris.data.assign(target=iris.target_names[iris.target])

weave.show(df)
```

<img src="/docs/assets/first_load.gif" width="100%">

**2. Add a plot**

<img src="./docs/assets/qs_table_plot.gif" width="100%">

**3. Create and share dashboards**

<img src="./docs/assets/make_quick_board.gif" width="100%">

## 👩‍🏫 Example Notebooks

Weave has example notebooks demonstrating common usage patterns. To use the notebooks, clone this repository and install the examples' dependencies:

```
pip install '.[examples]'
```

then run through the notebooks in the [examples directory](./examples)

## 🎉 Why Weave?

- 🚀 **Performant:** Weave is built with performance in mind. It's designed to handle large datasets smoothly so you can focus on what matters - exploring data and finding insights. Under the hood we optimize execution plans and parallelize computation using Arrow.
- 🎨 **Interactive:** Weave is all about making data exploration fun and interactive. It empowers you to engage with your data and discover patterns that static graphs can't reveal - without learning complicated APIs! Beautiful and interactive plots to bring your data to life.
- 🧩 **Modular Ecosystem:** Weave's architecture & compute language is build on Types, Ops, and Panels. Combine different components to build your customized data exploration toolkit, and publish reusable components into the ecosystem for others to use!
- 💻 **Open-Source:** We believe in the power of open-source. Weave is built by the community, for the community. We are excited to see how you use it and what you build with it.

---

## 📚 Getting Started

Before you dive in, make sure you have the required software installed. You'll find all the details in our [Installation Guide](./docs/INSTALLATION.md).

After installation, check out our [Quick Start Guide](./docs/QUICKSTART.md) to get a feel for Weave. For deeper dives, we recommend our [Example Notebooks](./examples/README.md), which are packed with detailed explanations, examples, and even some data exploration wizardry!

---

## 🎁 Feature Statuses

**Important:** Weave is newly open sourced and the APIs are subject to change. Please report any issues to [https://github.com/wandb/weave/issues](https://github.com/wandb/weave/issues).

**Statuses**:

- ✅: **Available:** The feature is relatively stable and ready for use
- 💡: **Preview:** The feature is code-complete, but may have some rough edges
- 🚧: **In Development:**: The feature is still in active development - while usable, expect changes.
- 📝: **Todo:**: The feature has not entered development

| **Category**       | **Feature**                                       | **Status** |
| ------------------ | ------------------------------------------------- | ---------- |
| **API**            |                                                   |            |
|                    | weave.save                                        | ✅         |
|                    | weave.show                                        | ✅         |
|                    | weave.publish                                     | 💡         |
| **Custom Objects** |                                                   |            |
|                    | Custom Types via @weave.type decorator            | 💡         |
|                    | Custom Ops via @weave.op decorator                | 💡         |
|                    | Custom Panels via weave.panels.Panel subclass     | 🚧         |
| **Persistence**    |                                                   |            |
|                    | Publish & Save Data                               | ✅         |
|                    | Publish & Save Custom Python Objects (eg. Models) | 💡         |
|                    | Publish & Save Configured Dashboards              | 💡         |
|                    | Publish & Save Panels, Ops, & Types               | 🚧         |
| **UX**             |                                                   |            |
|                    | Tables                                            | ✅         |
|                    | Plots                                             | ✅         |
|                    | Dashboard Editor                                  | 💡         |
|                    | Core Component Library                            | 💡         |
|                    | Code Export                                       | 💡         |
|                    | Media Types                                       | 🚧         |
|                    | Version Navigation                                | 🚧         |
| **Implementation** |                                                   |            |
|                    | Language Bindings (Python, JS)                    | ✅         |
|                    | Tests/Code coverage                               | ✅         |
|                    | Core Language Spec (Types, Ops, Panels)           | 💡         |
|                    | Benchmarks                                        | 📝         |
| **Materials**      |                                                   |            |
|                    | Examples                                          | ✅         |
|                    | Documentation (API Reference, Guides)             | 🚧         |

---

## 👩‍💻 Contribution

Are you passionate about data exploration and open-source projects? Awesome! Weave's community is always looking for contributors. Check out our [Contribution Guide](./docs/CONTRIBUTING.md) to learn how you can make Weave even better!

## 📢 Community

Join our thriving community [Discord](https://discord.gg/nNcvfX9GZ4). It's the perfect place to ask questions, share your projects, or just chat about data exploration.

## 💖 Thanks

Special thanks to everyone who has contributed to Weave, from submitting bug reports and feature requests to contributing code and documentation. Weave wouldn't be what it is today without you!

---

Happy Weaving! 🎉

**Made with 💜 by Weights and Biases**
