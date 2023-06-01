import {
  isTaggedValue,
  isUnion,
  mappableNullable,
  mappableNullableVal,
  maybe,
  taggedValue,
} from '../../model';
import {makeOp} from '../../opStore';
import {docType} from '../../util/docs';

// Not exposed, we should have more specific ops that
// get specific kinds of tags
export const opGetTag = makeOp({
  hidden: true,
  name: 'get-tag',
  argTypes: {
    value: maybe(taggedValue('any', 'any')),
  },
  description: `Returns the tag of a ${docType('tagged')}`,
  argDescriptions: {
    value: `The ${docType('tagged')}`,
  },
  returnValueDescription: `The tag of the ${docType('tagged')}`,
  returnType: inputs => {
    return mappableNullable(inputs.value.type, t => {
      if (isUnion(t)) {
        // Treating this as an error for now. It is likely the result
        // of a problem elsewhere. We should always have a specific single
        // tag, rather than a union of tags. TaggedValues are meant to
        // convey path information, you should never need to try two
        // different paths.
        throw new Error('opGetTag: expected input to not be a union');
        // return TypeHelpers.union(
        //   t.members.map(mem => {
        //     if (!TypeHelpers.isTaggedValue(mem)) {
        //       throw new Error('invalid');
        //     }
        //     return mem.tag;
        //   })
        // );
      }
      if (!isTaggedValue(t)) {
        throw new Error('opGetTag: expected input to be a tagged value');
      }
      return t.tag;
    });
  },
  resolver: inputs => mappableNullableVal(inputs.value, v => v._tag),
});
