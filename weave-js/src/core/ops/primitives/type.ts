import {defaultLanguageBinding} from '../../language/default';
import {isSimpleTypeShape, Type} from '../../model';
import {makeOp} from '../../opStore';
import {docType} from '../../util/docs';

// Not exposed yet. Needs to handle tags, nulls (see number.ts)

export const opTypeString = makeOp({
  hidden: true,
  name: 'type-string',
  argTypes: {type: 'type'},
  description: `Returns the ${docType('string')} representation of a ${docType(
    'type'
  )}`,
  argDescriptions: {type: `The ${docType('type')}`},
  returnValueDescription: `The ${docType(
    'string'
  )} representation of the ${docType('type')}`,
  returnType: 'string',
  resolver: async (inputs, forwardGraph, forwardOp, context) => {
    return defaultLanguageBinding.printType(inputs.type);
  },
});

export const opTypeName = makeOp({
  hidden: true,
  name: 'type-name',
  argTypes: {type: 'type'},
  returnType: 'string',
  resolver: async (inputs, forwardGraph, forwardOp, context) => {
    const weaveType: Type = inputs.type;
    if (isSimpleTypeShape(weaveType)) {
      return weaveType;
    }

    return weaveType.type;
  },
});
