import * as weave from '../src';

async function main() {
  // Initialize Weave
  await weave.init('attributes-example');

  // Define a simple op
  const greet = weave.op(async (name: string) => {
    return `Hello, ${name}!`;
  });

  // Example 1: Basic usage - set attributes for all calls within the scope
  console.log('\nExample 1: Basic usage');
  await weave.attributes({env: 'production', version: '1.0.0'}, async () => {
    await greet('Alice');
    await greet('Bob');
  });

  // Example 2: Nested attributes - inner attributes merge with outer ones
  console.log('\nExample 2: Nested attributes');
  await weave.attributes({env: 'staging'}, async () => {
    await weave.attributes({user_id: '123', feature_flag: 'beta'}, async () => {
      await greet('Charlie');
    });
  });

  // Example 3: Overwriting attributes - inner values take precedence
  console.log('\nExample 3: Overwriting attributes');
  await weave.attributes({env: 'production', region: 'us-west'}, async () => {
    await weave.attributes({env: 'staging'}, async () => {
      // This call will have env='staging' and region='us-west'
      await greet('David');
    });
  });

  // Example 4: Multiple operations in the same context
  console.log('\nExample 4: Multiple operations');
  const calculate = weave.op(async (a: number, b: number) => {
    return a + b;
  });

  await weave.attributes(
    {
      session_id: 'abc123',
      user_tier: 'premium',
    },
    async () => {
      await greet('Eve');
      await calculate(5, 3);
      await greet('Frank');
    }
  );

  // Example 5: Concurrent operations with different attributes
  // AsyncLocalStorage ensures each context is isolated
  console.log('\nExample 5: Concurrent operations (attributes are isolated)');
  await Promise.all([
    weave.attributes({user: 'alice', request_id: 'req-1'}, async () => {
      await greet('Alice');
      await calculate(10, 5);
    }),
    weave.attributes({user: 'bob', request_id: 'req-2'}, async () => {
      await greet('Bob');
      await calculate(20, 3);
    }),
    weave.attributes({user: 'charlie', request_id: 'req-3'}, async () => {
      await greet('Charlie');
      await calculate(15, 8);
    }),
  ]);

  console.log(
    '\nCheck the Weave UI to see the attributes attached to each call!'
  );
  console.log(
    'Notice how concurrent operations maintain their own separate attributes!'
  );
}

main().catch(console.error);

