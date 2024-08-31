# Weave (Alpha)

Weave is a library for tracing and monitoring AI applications.

This is an Alpha release, APIs are extremely subject to change.

## Installation

You can install Weave via npm:

```bash
npm install weave
```

Ensure you have a wandb API key in ~/.netrc.

Like

```
machine api.wandb.ai
  login user
  password <wandb-api-key>
```

Get your wandb API key from [here](https://wandb.ai/authorize).

## Quickstart

Put this in a file called `predict.mjs`:

```javascript
import { init, op, createPatchedOpenAI } from 'weave';

const openai = createPatchedOpenAI();

async function extractDinos(input) {
    const response = await openai.chat.completions.create({
        model: 'gpt-4o',
        messages: [{ role: 'user', content: `In JSON format extract a list of 'dinosaurs', with their 'name', their 'common_name', and whether its 'diet' is a herbivore or carnivore: ${input}` }],
    });
    return response.choices[0].message.content;
}
const extractDinosOp = op(extractDinos);

async function main() {
    await init('weave-quickstart');
    const result = await extractDinosOp("I watched as a Tyrannosaurus rex (T. rex) chased after a Triceratops (Trike), both carnivore and herbivore locked in an ancient dance. Meanwhile, a gentle giant Brachiosaurus (Brachi) calmly munched on treetops, blissfully unaware of the chaos below.");
    console.log(result);
}

main();
```

and then run

```
node predict.mjs
```

## Usage

### Initializing a Project

Before you can start tracing operations, you need to initialize a project. This sets up the necessary environment for trace collection.

```javascript
import { init } from 'weave';

// Initialize your project with a unique project name
init('my-awesome-ai-project');
```

### Tracing Operations

You can trace specific operations using the `op` function. This function wraps your existing functions and tracks their execution.

```javascript
import { op } from 'weave';

// Define a function you want to trace
async function myFunction(arg1, arg2) {
    // Your function logic
    return arg1 + arg2;
}

// Wrap the function with op to enable tracing
const tracedFunction = op(myFunction, 'myFunction');

// Call the traced function
tracedFunction(5, 10);
```

### OpenAI Integration

Weave provides an integration with OpenAI, allowing you to trace API calls made to OpenAI's services seamlessly.

```javascript
import { createPatchedOpenAI } from 'weave/integrations/openai';

// Create a patched instance of OpenAI with your API key
const openai = createPatchedOpenAI('your-openai-api-key');

// Use the OpenAI instance as usual
openai.chat.completions.create({
    model: 'text-davinci-003',
    prompt: 'Translate the following English text to French: "Hello, world!"',
    max_tokens: 60
});
```


## Configuration

Weave reads API keys from the `.netrc` file located in your home directory. Ensure you have the required API keys configured for seamless integration and tracking.

```
machine api.wandb.ai
  login user
  password <wandb-api-key>
```

Get your wandb API key from [here](https://wandb.ai/authorize).

## License

This project is licensed under the Apaache2 License - see the [LICENSE](../LICENSE) file for details.


### Roadmap / TODO

- [x] Return token counts
- [x] Summary merging
- [ ] Decide how to handle args in js, since they're not named
- [ ] Make sure LLM streaming is handled
- [ ] Op versioning / code capture
- [ ] Retry logic
- [ ] Include system information in call attributes including package version.
- [ ] Objects / Datasets / Models / Evaluations
- [ ] Ref tracking
- [ ] More integrations