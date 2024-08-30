import { init, op } from './src/clientApi';

// Initialize the API
init('shawn/weavejs-test1');

// Define a simple function to be wrapped
function add(a: number, b: number): number {
    return a + b;
}

// Wrap the function using op
const wrappedAdd = op(add);

// Function to demonstrate async behavior
async function delayedMultiply(a: number, b: number): Promise<number> {
    await new Promise(resolve => setTimeout(resolve, 1000)); // 1 second delay
    return a * b;
}

// Wrap the async function
const wrappedDelayedMultiply = op(delayedMultiply);

// Function to demonstrate nested calls
async function complexOperation(a: number, b: number, c: number): Promise<number> {
    const sum = await wrappedAdd(a, b);
    const product = await wrappedDelayedMultiply(sum, c);
    return product;
}

// Wrap the complex function
const wrappedComplexOperation = op(complexOperation);

// Main async function to run our tests
async function runTests() {
    console.log('Starting tests...');

    // Test the wrapped add function
    console.log('Testing wrapped add function:');
    console.log('2 + 3 =', await wrappedAdd(2, 3));

    // Test the wrapped async multiply function
    console.log('\nTesting wrapped delayed multiply function:');
    console.log('3 * 4 =', await wrappedDelayedMultiply(3, 4));

    // Test the complex operation with nested calls
    console.log('\nTesting complex operation with nested calls:');
    console.log('(2 + 3) * 4 =', await wrappedComplexOperation(2, 3, 4));

    console.log('\nTests completed.');
}

// Run the tests
runTests().catch(error => console.error('An error occurred:', error));