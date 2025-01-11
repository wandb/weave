require('dotenv').config();

import { OpenAI } from 'openai';
import * as weave from 'weave';

/**
 * # 🚀 Weave Quickstart Guide
 * 
 * Get started using Weave to:
 * - Log and debug language model inputs, outputs, and traces
 * - Build rigorous, apples-to-apples evaluations for language model use cases
 * - Organize all the information generated across the LLM workflow, from experimentation to evaluations to production
 * 
 * See the full Weave documentation [here](https://wandb.me/weave).
 */

/**
 * ## 📝 Function Tracking
 * 
 * Add the weave.op wrapper to the functions you want to track.
 * After adding weave.op and calling the function, visit the W&B dashboard 
 * to see it tracked within your project.
 * 
 * 💡 We automatically track your code - check the code tab in the UI!
 */

/**
 * Initializes the Weave project
 */
async function initializeWeaveProject() {
    const PROJECT = 'weave-examples';
    await weave.init(PROJECT);
}

const stripUserInput = weave.op(function stripUserInput(userInput: string): string {
    return userInput.trim();
});

/**
 * Track a simple function call with Weave.
 * This example shows how basic function tracking works.
 */
async function demonstrateBasicTracking() {
    const result = await stripUserInput("    hello    ");
    console.log('Basic tracking result:', result);
}

/**
 * ## 🔌 OpenAI Integration
 * 
 * Track OpenAI API calls with Weave.
 * All OpenAI calls are automatically tracked, including:
 * - Token usage
 * - API costs
 * - Request/response pairs
 * - Model configurations
 * 
 * Note: We also support other LLM providers like Anthropic and Mistral.
 */
function initializeOpenAIClient() {
    return weave.wrapOpenAI(new OpenAI({
        apiKey: process.env.OPENAI_API_KEY
    }));
}

async function demonstrateOpenAITracking() {
    const client = initializeOpenAIClient();
    const result = await client.chat.completions.create({
        model: "gpt-4-turbo",
        messages: [{ role: "user", content: "Hello, how are you?" }],
    });
    console.log('OpenAI tracking result:', result);
}

/**
 * ## 🔄 Nested Function Tracking
 * 
 * Track complex workflows by combining multiple tracked functions
 * and LLM calls while preserving the entire execution trace.
 * This enables:
 * - Full visibility into your application's logic flow
 * - Debugging of complex chains of operations
 * - Performance optimization opportunities
 */
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

/**
 * ## 📊 Dataset Management
 * 
 * Create and manage datasets with Weave.
 * Similar to models, weave.Dataset helps:
 * - Track and version your data
 * - Organize test cases
 * - Share datasets between team members
 * - Power systematic evaluations
 */

interface GrammarExample {
    userInput: string;
    expected: string;
}

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
                userInput: "GPT-4 is smartest AI model.",
                expected: "GPT-4 is the smartest AI model."
            }
        ]
    });
}

/**
 * ## 📈 Evaluation Framework
 * 
 * Run systematic evaluations with Weave.
 * Evaluation-driven development helps you reliably iterate on an application.
 * The Evaluation class:
 * - Assesses Model performance on a Dataset
 * - Applies custom scoring functions
 * - Generates detailed performance reports
 * - Enables comparison between model versions
 * 
 * See the full evaluation tutorial at: http://wandb.me/weave_eval_tut
 */

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

/**
 * Main function to run all demonstrations
 */
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

// Execute the main function
if (require.main === module) {
    main();
}
