import {maybe} from '../../model';
import {makeOp} from '../../opStore';

export const opWeaveServerVersion = makeOp({
  hidden: true,
  name: 'executionEngine-serverVersion',
  argTypes: {},
  returnType: maybe('string'),
  resolver: () => {
    return null;
  },
});
