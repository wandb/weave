import * as OpKinds from '../opKinds';

const makeRunQueueOp = OpKinds.makeTaggingStandardOp;

const runQueueArgTypes = {
  runQueue: 'runQueue' as const,
};

export const opRunQueueId = makeRunQueueOp({
  hidden: true,
  name: 'runQueue-id',
  argTypes: runQueueArgTypes,
  returnType: inputTypes => 'string',
  resolver: ({runQueue}) => {
    return runQueue.Id;
  },
});

// TODO: add run queue items and other ops for runQueues
