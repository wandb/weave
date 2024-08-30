# Weave

Weave is a library for tracing and monitoring AI applications.

## Installation

You can install Weave via npm:

```bash
npm install weave
```

## Usage

### Initializing a Project

Before you can start tracing operations, you need to initialize a project. This sets up the necessary environment for trace collection.

```javascript
import { init } from 'weave';

// Initialize your project with a unique project name
init('<teamname>/my-awesome-ai-project');
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

## Contributing

We welcome contributions! Please read our [contributing guidelines](CONTRIBUTING.md) before making a pull request.

## License

This project is licensed under the Apaache2 License - see the [LICENSE](../LICENSE) file for details.
