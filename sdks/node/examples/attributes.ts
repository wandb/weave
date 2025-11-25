import {init, op, withAttributes} from 'weave';

// Simple child op so we can verify propagation
const childOp = op(async function childOp(input: string) {
  return `child saw: ${input}`;
});

const parentOp = op(async function parentOp(input: string) {
  const childResult = await childOp(input);
  return {parent: input, childResult};
});

async function main() {
  // Replace with your entity/project
  await init('your-entity/your-project', {
    globalAttributes: {tenant: 'acme-co', env: 'prod'},
  });

  const result = await withAttributes(
    {requestId: 'req-123', env: 'prod-override'},
    async () => parentOp('weave attribute context example')
  );

  console.log('Result:', result);
  console.log(
    'Calls in the UI will have tenant/requestId/env on both parent and child.'
  );
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
