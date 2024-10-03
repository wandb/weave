"use strict";(self.webpackChunkdocs=self.webpackChunkdocs||[]).push([[5577],{2344:(e,n,t)=>{t.r(n),t.d(n,{assets:()=>l,contentTitle:()=>s,default:()=>h,frontMatter:()=>o,metadata:()=>r,toc:()=>c});var a=t(85893),i=t(11151);const o={},s="Tutorial: Build an Evaluation pipeline",r={id:"tutorial-eval",title:"Tutorial: Build an Evaluation pipeline",description:"To iterate on an application, we need a way to evaluate if it's improving. To do so, a common practice is to test it against the same set of examples when there is a change. Weave has a first-class way to track evaluations with Model & Evaluation classes. We have built the APIs to make minimal assumptions to allow for the flexibility to support a wide array of use-cases.",source:"@site/docs/tutorial-eval.md",sourceDirName:".",slug:"/tutorial-eval",permalink:"/tutorial-eval",draft:!1,unlisted:!1,editUrl:"https://github.com/wandb/weave/blob/master/docs/docs/tutorial-eval.md",tags:[],version:"current",lastUpdatedAt:1727953082e3,frontMatter:{},sidebar:"documentationSidebar",previous:{title:"App versioning",permalink:"/tutorial-weave_models"},next:{title:"Evaluate a RAG App",permalink:"/tutorial-rag"}},l={},c=[{value:"1. Build a <code>Model</code>",id:"1-build-a-model",level:2},{value:"2. Collect some examples",id:"2-collect-some-examples",level:2},{value:"3. Evaluate a <code>Model</code>",id:"3-evaluate-a-model",level:2},{value:"4. Pulling it all together",id:"4-pulling-it-all-together",level:2},{value:"What&#39;s next?",id:"whats-next",level:2}];function d(e){const n={a:"a",admonition:"admonition",code:"code",h1:"h1",h2:"h2",img:"img",li:"li",p:"p",pre:"pre",strong:"strong",ul:"ul",...(0,i.a)(),...e.components};return(0,a.jsxs)(a.Fragment,{children:[(0,a.jsx)(n.h1,{id:"tutorial-build-an-evaluation-pipeline",children:"Tutorial: Build an Evaluation pipeline"}),"\n",(0,a.jsxs)(n.p,{children:["To iterate on an application, we need a way to evaluate if it's improving. To do so, a common practice is to test it against the same set of examples when there is a change. Weave has a first-class way to track evaluations with ",(0,a.jsx)(n.code,{children:"Model"})," & ",(0,a.jsx)(n.code,{children:"Evaluation"})," classes. We have built the APIs to make minimal assumptions to allow for the flexibility to support a wide array of use-cases."]}),"\n",(0,a.jsx)(n.p,{children:(0,a.jsx)(n.img,{alt:"Evals hero",src:t(65259).Z+"",width:"4100",height:"2160"})}),"\n",(0,a.jsxs)(n.h2,{id:"1-build-a-model",children:["1. Build a ",(0,a.jsx)(n.code,{children:"Model"})]}),"\n",(0,a.jsxs)(n.p,{children:[(0,a.jsx)(n.code,{children:"Model"}),"s store and version information about your system, such as prompts, temperatures, and more.\nWeave automatically captures when they are used and update the version when there are changes."]}),"\n",(0,a.jsxs)(n.p,{children:[(0,a.jsx)(n.code,{children:"Model"}),"s are declared by subclassing ",(0,a.jsx)(n.code,{children:"Model"})," and implementing a ",(0,a.jsx)(n.code,{children:"predict"})," function definition, which takes one example and returns the response."]}),"\n",(0,a.jsx)(n.admonition,{type:"warning",children:(0,a.jsxs)(n.p,{children:[(0,a.jsx)(n.strong,{children:"Known Issue"}),": If you are using Google Colab, remove ",(0,a.jsx)(n.code,{children:"async"})," from the following examples."]})}),"\n",(0,a.jsx)(n.pre,{children:(0,a.jsx)(n.code,{className:"language-python",children:'import json\nimport openai\nimport weave\n\n# highlight-next-line\nclass ExtractFruitsModel(weave.Model):\n    model_name: str\n    prompt_template: str\n\n    # highlight-next-line\n    @weave.op()\n    # highlight-next-line\n    async def predict(self, sentence: str) -> dict:\n        client = openai.AsyncClient()\n\n        response = await client.chat.completions.create(\n            model=self.model_name,\n            messages=[\n                {"role": "user", "content": self.prompt_template.format(sentence=sentence)}\n            ],\n        )\n        result = response.choices[0].message.content\n        if result is None:\n            raise ValueError("No response from model")\n        parsed = json.loads(result)\n        return parsed\n'})}),"\n",(0,a.jsxs)(n.p,{children:["You can instantiate ",(0,a.jsx)(n.code,{children:"Model"})," objects as normal like this:"]}),"\n",(0,a.jsx)(n.pre,{children:(0,a.jsx)(n.code,{className:"language-python",children:'import asyncio\nimport weave\n\nweave.init(\'intro-example\')\n\nmodel = ExtractFruitsModel(model_name=\'gpt-3.5-turbo-1106\',\n                          prompt_template=\'Extract fields ("fruit": <str>, "color": <str>, "flavor": <str>) from the following text, as json: {sentence}\')\nsentence = "There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy."\nprint(asyncio.run(model.predict(sentence)))\n# if you\'re in a Jupyter Notebook, run:\n# await model.predict(sentence)\n'})}),"\n",(0,a.jsx)(n.admonition,{type:"note",children:(0,a.jsxs)(n.p,{children:["Checkout the ",(0,a.jsx)(n.a,{href:"/guides/core-types/models",children:"Models"})," guide to learn more."]})}),"\n",(0,a.jsx)(n.h2,{id:"2-collect-some-examples",children:"2. Collect some examples"}),"\n",(0,a.jsx)(n.pre,{children:(0,a.jsx)(n.code,{className:"language-python",children:"sentences = [\"There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy.\",\n\"Pounits are a bright green color and are more savory than sweet.\",\n\"Finally, there are fruits called glowls, which have a very sour and bitter taste which is acidic and caustic, and a pale orange tinge to them.\"]\nlabels = [\n    {'fruit': 'neoskizzles', 'color': 'purple', 'flavor': 'candy'},\n    {'fruit': 'pounits', 'color': 'bright green', 'flavor': 'savory'},\n    {'fruit': 'glowls', 'color': 'pale orange', 'flavor': 'sour and bitter'}\n]\nexamples = [\n    {'id': '0', 'sentence': sentences[0], 'target': labels[0]},\n    {'id': '1', 'sentence': sentences[1], 'target': labels[1]},\n    {'id': '2', 'sentence': sentences[2], 'target': labels[2]}\n]\n"})}),"\n",(0,a.jsxs)(n.h2,{id:"3-evaluate-a-model",children:["3. Evaluate a ",(0,a.jsx)(n.code,{children:"Model"})]}),"\n",(0,a.jsxs)(n.p,{children:[(0,a.jsx)(n.code,{children:"Evaluation"}),"s assess a ",(0,a.jsx)(n.code,{children:"Model"}),"s performance on a set of examples using a list of specified scoring functions or ",(0,a.jsx)(n.code,{children:"weave.flow.scorer.Scorer"})," classes."]}),"\n",(0,a.jsxs)(n.p,{children:["Here, we'll use a default scoring class ",(0,a.jsx)(n.code,{children:"MultiTaskBinaryClassificationF1"})," and we'll also define our own ",(0,a.jsx)(n.code,{children:"fruit_name_score"})," scoring function."]}),"\n",(0,a.jsxs)(n.p,{children:["Here ",(0,a.jsx)(n.code,{children:"sentence"})," is passed to the model's predict function, and ",(0,a.jsx)(n.code,{children:"target"})," is used in the scoring function, these are inferred based on the argument names of the ",(0,a.jsx)(n.code,{children:"predict"})," and scoring functions. The ",(0,a.jsx)(n.code,{children:"fruit"})," key needs to be outputted by the model's predict function and must also be existing as a column in the dataset (or outputted by the ",(0,a.jsx)(n.code,{children:"preprocess_model_input"})," function if defined)."]}),"\n",(0,a.jsx)(n.pre,{children:(0,a.jsx)(n.code,{className:"language-python",children:"import weave\nfrom weave.flow.scorer import MultiTaskBinaryClassificationF1\n\nweave.init('intro-example')\n\n@weave.op()\ndef fruit_name_score(target: dict, model_output: dict) -> dict:\n    return {'correct': target['fruit'] == model_output['fruit']}\n\n# highlight-next-line\nevaluation = weave.Evaluation(\n    # highlight-next-line\n    dataset=examples,\n    # highlight-next-line\n    scorers=[\n        # highlight-next-line\n        MultiTaskBinaryClassificationF1(class_names=[\"fruit\", \"color\", \"flavor\"]),\n        # highlight-next-line\n        fruit_name_score\n    # highlight-next-line\n    ],\n# highlight-next-line\n)\n# highlight-next-line\nprint(asyncio.run(evaluation.evaluate(model)))\n# if you're in a Jupyter Notebook, run:\n# await evaluation.evaluate(model)\n"})}),"\n",(0,a.jsxs)(n.p,{children:["In some applications we want to create custom ",(0,a.jsx)(n.code,{children:"Scorer"})," classes - where for example a standardized ",(0,a.jsx)(n.code,{children:"LLMJudge"})," class should be created with specific parameters (e.g. chat model, prompt), specific scoring of each row, and specific calculation of an aggregate score. See the tutorial on defining a ",(0,a.jsx)(n.code,{children:"Scorer"})," class in the next chapter on ",(0,a.jsx)(n.a,{href:"/tutorial-rag#optional-defining-a-scorer-class",children:"Model-Based Evaluation of RAG applications"})," for more information."]}),"\n",(0,a.jsx)(n.h2,{id:"4-pulling-it-all-together",children:"4. Pulling it all together"}),"\n",(0,a.jsx)(n.pre,{children:(0,a.jsx)(n.code,{className:"language-python",children:"import json\nimport asyncio\n# highlight-next-line\nimport weave\n# highlight-next-line\nfrom weave.flow.scorer import MultiTaskBinaryClassificationF1\nimport openai\n\n# We create a model class with one predict function.\n# All inputs, predictions and parameters are automatically captured for easy inspection.\n\n# highlight-next-line\nclass ExtractFruitsModel(weave.Model):\n    model_name: str\n    prompt_template: str\n\n    # highlight-next-line\n    @weave.op()\n    # highlight-next-line\n    async def predict(self, sentence: str) -> dict:\n        client = openai.AsyncClient()\n\n        response = await client.chat.completions.create(\n            model=self.model_name,\n            messages=[\n                {\"role\": \"user\", \"content\": self.prompt_template.format(sentence=sentence)}\n            ],\n            response_format={ \"type\": \"json_object\" }\n        )\n        result = response.choices[0].message.content\n        if result is None:\n            raise ValueError(\"No response from model\")\n        parsed = json.loads(result)\n        return parsed\n\n# We call init to begin capturing data in the project, intro-example.\nweave.init('intro-example')\n\n# We create our model with our system prompt.\nmodel = ExtractFruitsModel(name='gpt4',\n                           model_name='gpt-4-0125-preview',\n                           prompt_template='Extract fields (\"fruit\": <str>, \"color\": <str>, \"flavor\") from the following text, as json: {sentence}')\nsentences = [\"There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy.\",\n\"Pounits are a bright green color and are more savory than sweet.\",\n\"Finally, there are fruits called glowls, which have a very sour and bitter taste which is acidic and caustic, and a pale orange tinge to them.\"]\nlabels = [\n    {'fruit': 'neoskizzles', 'color': 'purple', 'flavor': 'candy'},\n    {'fruit': 'pounits', 'color': 'bright green', 'flavor': 'savory'},\n    {'fruit': 'glowls', 'color': 'pale orange', 'flavor': 'sour and bitter'}\n]\nexamples = [\n    {'id': '0', 'sentence': sentences[0], 'target': labels[0]},\n    {'id': '1', 'sentence': sentences[1], 'target': labels[1]},\n    {'id': '2', 'sentence': sentences[2], 'target': labels[2]}\n]\n# If you have already published the Dataset, you can run:\n# dataset = weave.ref('example_labels').get()\n\n# We define a scoring functions to compare our model predictions with a ground truth label.\n@weave.op()\ndef fruit_name_score(target: dict, model_output: dict) -> dict:\n    return {'correct': target['fruit'] == model_output['fruit']}\n\n# Finally, we run an evaluation of this model.\n# This will generate a prediction for each input example, and then score it with each scoring function.\n# highlight-next-line\nevaluation = weave.Evaluation(\n    name='fruit_eval',\n    # highlight-next-line\n    dataset=examples, scorers=[MultiTaskBinaryClassificationF1(class_names=[\"fruit\", \"color\", \"flavor\"]), fruit_name_score],\n# highlight-next-line\n)\nprint(asyncio.run(evaluation.evaluate(model)))\n# if you're in a Jupyter Notebook, run:\n# await evaluation.evaluate(model)\n"})}),"\n",(0,a.jsx)(n.h2,{id:"whats-next",children:"What's next?"}),"\n",(0,a.jsxs)(n.ul,{children:["\n",(0,a.jsxs)(n.li,{children:["Follow the ",(0,a.jsx)(n.a,{href:"/tutorial-rag",children:"Model-Based Evaluation of RAG applications"})," to evaluate a RAG app using an LLM judge."]}),"\n"]})]})}function h(e={}){const{wrapper:n}={...(0,i.a)(),...e.components};return n?(0,a.jsx)(n,{...e,children:(0,a.jsx)(d,{...e})}):d(e)}},65259:(e,n,t)=>{t.d(n,{Z:()=>a});const a=t.p+"assets/images/evals-hero-eaaf7b203721d2a352cb2facba3dcd92.png"},11151:(e,n,t)=>{t.d(n,{Z:()=>r,a:()=>s});var a=t(67294);const i={},o=a.createContext(i);function s(e){const n=a.useContext(o);return a.useMemo((function(){return"function"==typeof e?e(n):{...n,...e}}),[n,e])}function r(e){let n;return n=e.disableParentContext?"function"==typeof e.components?e.components(i):e.components||i:s(e.components),a.createElement(o.Provider,{value:n},e.children)}}}]);