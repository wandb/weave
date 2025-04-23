# Weave with TypeScript Quickstart Guide

You can use W&B Weave with Typescript to:

- Log and debug language model inputs, outputs, and traces
- Build rigorous, apples-to-apples evaluations for language model use cases
- Organize all the information generated across the LLM workflow, from experimentation to evaluations to production

For more information, see the [Weave documentation](/). 

## Function tracking

To use Weave in your Typescript code, initialize a new Weave project and add the `weave.op` wrapper to the functions you want to track.

After adding `weave.op` and calling the function, visit the W&B dashboard to see it tracked within your project.

We automatically track your code - check the code tab in the UI!

```typescript
async function initializeWeaveProject() {
    const PROJECT = 'weave-examples';
    await weave.init(PROJECT);
}
```

```typescript
const stripUserInput = weave.op(function stripUserInput(userInput: string): string {
    return userInput.trim();
});
```

The following example shows how basic function tracking works.

```typescript
async function demonstrateBasicTracking() {
    const result = await stripUserInput("    hello    ");
    console.log('Basic tracking result:', result);
}
```

## OpenAI integration

Weave automatically tracks all OpenAI calls, including:

- Token usage
- API costs
- Request/response pairs
- Model configurations

:::note
In addition to OpenAI, Weave supports automatic logging of other LLM providers, such as Anthropic and Mistral. For the full list, see [LLM Providers in the Integrations documentation](../../guides/integrations/index.md#llm-providers).
:::

```typescript
function initializeOpenAIClient() {
    return weave.wrapOpenAI(new OpenAI({
        apiKey: process.env.OPENAI_API_KEY
    }));
}
```

```typescript
async function demonstrateOpenAITracking() {
    const client = initializeOpenAIClient();
    const result = await client.chat.completions.create({
        model: "gpt-4-turbo",
        messages: [{ role: "user", content: "Hello, how are you?" }],
    });
    console.log('OpenAI tracking result:', result);
}
```

## Nested function tracking

Weave allows you to track complex workflows by combining multiple tracked functions
and LLM calls while preserving the entire execution trace. The benefits of this include:

- Full visibility into your application's logic flow
- Easy debugging of complex chains of operations
- Performance optimization opportunities

```typescript
async function demonstrateNestedTracking() {
    const client = initializeOpenAIClient();
    
    const correctGrammar = weave.op(async function correctGrammar(userInput: string): Promise<string> {
        const stripped = await stripUserInput(userInput);
        const response = await client.chat.completions.create({
            model: "gpt-4-turbo",
            messages: [
                {
                    role: "system",
                    content: "You are a grammar checker, correct the following user input."
                },
                { role: "user", content: stripped }
            ],
            temperature: 0,
        });
        return response.choices[0].message.content ?? '';
    });

    const grammarResult = await correctGrammar("That was so easy, it was a piece of pie!");
    console.log('Nested tracking result:', grammarResult);
}
```

## Dataset management

You can create and manage datasets with Weave using the [`weave.Dataset`](../../guides/core-types/datasets.md) class. Similar to [Weave `Models`](../../guides/core-types/models.md), `weave.Dataset` helps:

- Track and version your data
- Organize test cases
- Share datasets between team members
- Power systematic evaluations

```typescript
interface GrammarExample {
    userInput: string;
    expected: string;
}
```

```typescript
function createGrammarDataset(): weave.Dataset<GrammarExample> {
    return new weave.Dataset<GrammarExample>({
        id: 'grammar-correction',
        rows: [
            {
                userInput: "That was so easy, it was a piece of pie!",
                expected: "That was so easy, it was a piece of cake!"
            },
            {
                userInput: "I write good",
                expected: "I write well"
            },
            {
                userInput: "LLM's are best",
                expected: "LLM's are the best"
            }
        ]
    });
}
```

## Evaluation framework

Weave supports evaluation-driven development with the [`Evaluation` class](../../guides/core-types/evaluations.md). Evaluations help you reliably iterate on your GenAI application. The `Evaluation` class does the following:

- Assesses `Model` performance on a `Dataset`
- Applies custom scoring functions
- Generates detailed performance reports
- Enables comparison between model versions

You can find a complete evaluation tutorial at [http://wandb.me/weave_eval_tut](http://wandb.me/weave_eval_tut)

```typescript
class OpenAIGrammarCorrector {
    private oaiClient: ReturnType<typeof weave.wrapOpenAI>;
    
    constructor() {
        this.oaiClient = weave.wrapOpenAI(new OpenAI({
            apiKey: process.env.OPENAI_API_KEY
        }));
        this.predict = weave.op(this, this.predict);
    }

    async predict(userInput: string): Promise<string> {
        const response = await this.oaiClient.chat.completions.create({
            model: 'gpt-4-turbo',
            messages: [
                { 
                    role: "system", 
                    content: "You are a grammar checker, correct the following user input." 
                },
                { role: "user", content: userInput }
            ],
            temperature: 0
        });
        return response.choices[0].message.content ?? '';
    }
}
```

```typescript
async function runEvaluation() {
    const corrector = new OpenAIGrammarCorrector();
    const dataset = createGrammarDataset();
    
    const exactMatch = weave.op(
        function exactMatch({ modelOutput, datasetRow }: { 
            modelOutput: string; 
            datasetRow: GrammarExample 
        }): { match: boolean } {
            return { match: datasetRow.expected === modelOutput };
        },
        { name: 'exactMatch' }
    );

    const evaluation = new weave.Evaluation({
        dataset,
        scorers: [exactMatch],
    });

    const summary = await evaluation.evaluate({
        model: weave.op((args: { datasetRow: GrammarExample }) => 
            corrector.predict(args.datasetRow.userInput)
        )
    });
    console.log('Evaluation summary:', summary);
}
```

The following `main` function runs all demonstrations:

```typescript
async function main() {
    try {
        await initializeWeaveProject();
        await demonstrateBasicTracking();
        await demonstrateOpenAITracking();
        await demonstrateNestedTracking();
        await runEvaluation();
    } catch (error) {
        console.error('Error running demonstrations:', error);
    }
}
```