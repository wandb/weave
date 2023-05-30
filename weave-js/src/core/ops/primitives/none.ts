import {isConcreteTaggedValue, maybe} from '../../model';
import {makeOp} from '../../opStore';

// Warning: not projected
export const opIsNone = makeOp({
  name: 'isNone',
  argTypes: {
    val: maybe('any' as const),
  },
  description: 'Determines if the value is None.',
  argDescriptions: {
    val: 'Possibly None value.',
  },
  returnValueDescription: 'True if the value is None.',
  returnType: inputTypes => 'boolean' as const,
  resolver: ({val}) => {
    if (isConcreteTaggedValue(val)) {
      val = val._value;
    }
    return val == null;
  },
});
