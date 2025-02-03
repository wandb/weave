import OpenAI from 'openai';
import * as weave from 'weave';

// Initialize the API
weave.init('examples');

// Create OpenAI client
const openai = weave.wrapOpenAI(new OpenAI());

// Define a simple function to be wrapped
function add(a: number, b: number): number {
  return a + b;
}

// Wrap the function using op
const wrappedAdd = weave.op(add);

// Function to demonstrate async behavior
async function delayedMultiply(a: number, b: number): Promise<number> {
  await new Promise(resolve => setTimeout(resolve, 1000)); // 1 second delay
  return a * b;
}

// Wrap the async function
const wrappedDelayedMultiply = weave.op(delayedMultiply);

// Function to call OpenAI
async function callOpenAI(prompt: string): Promise<string> {
  const completion = await openai.chat.completions.create({
    model: 'gpt-3.5-turbo',
    messages: [{ role: 'user', content: prompt }],
  });
  return completion.choices[0].message.content || '';
}

// Wrap the OpenAI function
const wrappedCallOpenAI = weave.op(callOpenAI);

// Function to demonstrate nested calls including OpenAI
async function complexOperationWithAI(a: number, b: number, c: number): Promise<string> {
  const sum = await wrappedAdd(a, b);
  const product = await wrappedDelayedMultiply(sum, c);
  const prompt = `What is an interesting fact about the number ${product}?`;
  const aiResponse = await wrappedCallOpenAI(prompt);
  return `The result of the calculation is ${product}. ${aiResponse}`;
}

// Wrap the complex function
const wrappedComplexOperationWithAI = weave.op(complexOperationWithAI);

// Main async function to run our tests
async function runTests() {
  console.log('Starting tests...');

  // Test the wrapped add function
  console.log('\nTesting wrapped add function:');
  console.log('2 + 3 =', await wrappedAdd(2, 3));

  // Test the wrapped async multiply function
  console.log('\nTesting wrapped delayed multiply function:');
  console.log('3 * 4 =', await wrappedDelayedMultiply(3, 4));

  // Test the complex operation with nested calls including OpenAI
  console.log('\nTesting complex operation with nested calls including OpenAI:');
  const result = await wrappedComplexOperationWithAI(2, 3, 4);
  console.log(result);

  console.log('\nTests completed.');
}

// Run the tests
runTests().catch(error => console.error('An error occurred:', error));
