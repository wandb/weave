import _, {max} from 'lodash';

import type {Type} from '../../model';
import {
  concreteTaggedValue,
  getValueFromTaggedValue,
  isConcreteTaggedValue,
  isListLike,
  isNullable,
  isTaggedValue,
  list,
  listObjectType,
  maybe,
  nonNullable,
  nullableOneOrMany,
  taggedValue,
  union,
} from '../../model';
import {makeOp} from '../../opStore';

const nullable = (type: Type) => {
  return type === 'none' || isNullable(type);
};

const listLike = (type: Type) => {
  return isListLike(nonNullable(type));
};

const listObjIsNullable = (type: Type) => {
  return nullable(listObjectType(nonNullable(type)));
};

const NLN = (type: Type) => {
  return nullable(type) && listLike(type) && listObjIsNullable(type);
};

const NLC = (type: Type) => {
  return nullable(type) && listLike(type) && !listObjIsNullable(type);
};

const NS = (type: Type) => {
  return nullable(type) && !listLike(type);
};

const CLN = (type: Type) => {
  return !nullable(type) && listLike(type) && listObjIsNullable(type);
};

const CLC = (type: Type) => {
  return !nullable(type) && listLike(type) && !listObjIsNullable(type);
};

const CS = (type: Type) => {
  return !nullable(type) && !listLike(type);
};

export const opNoneCoalesce = makeOp({
  hidden: true,
  name: 'none-coalesce',
  argTypes: {
    lhs: nullableOneOrMany('any'),
    rhs: nullableOneOrMany('any'),
  },
  description:
    'Returns the second value if the first is null, otherwise the first value',
  argDescriptions: {
    lhs: 'The first value',
    rhs: 'The second value',
  },
  returnValueDescription:
    'The second value if the first is null, otherwise the first value',
  returnType: inputs => {
    /*
    type options: CS, NS, CLC, CLN, NLC, NLN
    nullable? (nullable is either none or maybe)
      |-Y- listlike?
      |       |-Y- listObjIsNullable?
      |       |         |-Y-------- NLN
      |       |         |-N-------- NLC
      |       |
      |       |-N------------------ NS
      |
      |-N- listlike?
              |-Y- listObjIsNullable?
              |         |-Y-------- CLN
              |         |
              |         |-N-------- CLC
              |
              |-N------------------ CS

                    RHS
                  CS | NS
              CS    lhs
              NS    union<nonnull<lhs>, rhs>
      LHS     CLC   lhs
              CLN   list<union<nonnull<lhs.objtype>, rhs>>
              NLC   union<nonnull<lhs>, rhs>
              NLN   union<rhs, list<union<nonnull<nonnull<lhs>.objtype>, rhs>>>

                     RHS
                  CLC | CLN
              CS    lhs
              NS    union<nonnull<lhs>, rhs>
      LHS     CLC   lhs
              CLN   list<union<nonnull<lhs.objtype>, rhs.objtype>>
              NLC   union<nonnull<lhs>, rhs>
              NLN   union<rhs, list<union<nonnull<nonnull<lhs>.objtype>, rhs.objtype>>>

                      RHS
                  NLC | NLN
              CS    lhs
              NS    union<nonnull<lhs>, rhs>
      LHS     CLC   lhs
              CLN   union<lhs, list<union<lhs.objtype, rhs.objtype>>>
              NLC   union<nonnull<lhs>, rhs>
              NLN   union<rhs, list<union<nonnull<nonnull<lhs>.objtype>, nonnull<rhs>.objtype>>>
    */
    const lhs = isTaggedValue(inputs.lhs.type)
      ? inputs.lhs.type.value
      : inputs.lhs.type;
    const lhsTagged = (type: Type) => {
      return isTaggedValue(inputs.lhs.type)
        ? taggedValue(inputs.lhs.type.tag, type)
        : type;
    };
    const rhs = isTaggedValue(inputs.rhs.type)
      ? inputs.rhs.type.value
      : inputs.rhs.type;
    const rhsTagged = (type: Type) => {
      return isTaggedValue(inputs.rhs.type)
        ? taggedValue(inputs.rhs.type.tag, type)
        : type;
    };

    if (CS(lhs)) {
      // lhs: CS
      // When the lhs is a concrete, single value, nothing changes
      // = lhs
      return lhsTagged(lhs);
    }

    if (NS(lhs)) {
      // lhs: NS
      // When the lhs is a nullable, singe value, return the union of nonnull lhs and rhs
      // = union<nonnull<lhs>, rhs>
      const nonNullLhs = nonNullable(lhs);
      if (nonNullLhs === 'none') {
        return inputs.rhs.type;
      }
      return union([lhsTagged(nonNullable(lhs)), inputs.rhs.type]);
    }

    if (CLC(lhs)) {
      // lhs: CLC
      // When the lhs is a concrete list of concrete values, nothing changes
      // = lhs
      return lhsTagged(lhs);
    }

    if (CLN(lhs)) {
      // lhs: CLN
      // When the lhs is concrete list of nullable values, the return type depends on the rhs

      if (CS(rhs) || NS(rhs)) {
        // rhs: CS || NS
        // when rhs is a concrete value or nullable value, possibly replace the list object type
        // = list<union<nonnull<lhs.objtype>, rhs>>
        return list(
          union([lhsTagged(nonNullable(listObjectType(lhs))), rhsTagged(rhs)])
        );
      }

      if (CLC(rhs) || CLN(rhs)) {
        // rhs: CLC || CLN
        // when rhs is a concrete list of anything, possibly replace the object type with the rhs object type
        // = list<union<nonnull<lhs.objtype>, rhs.objtype>>
        return list(
          union([
            lhsTagged(nonNullable(listObjectType(lhs))),
            rhsTagged(listObjectType(rhs)),
          ])
        );
      }

      if (NLC(rhs) || NLN(rhs)) {
        // rhs: NLC || NLN
        // when the rhs is a nullable version of the above, return lhs unioned with the above
        // = union<lhs, list<union<lhs.objtype, rhs.objtype>>>
        return union([
          lhs,
          list(
            union([
              lhsTagged(nonNullable(listObjectType(lhs))),
              rhsTagged(listObjectType(rhs)),
            ])
          ),
        ]);
      }
    }

    if (NLC(lhs)) {
      // lhs: NLC
      // when the lhs is a nullable list of concrete values, return nonnull lhs or rhs
      // union<nonnull<lhs>, rhs>
      return union([lhsTagged(nonNullable(lhs)), rhsTagged(rhs)]);
    }

    if (NLN(lhs)) {
      // lhs: NLN
      // when the lhs is a nullable list of nullable, depends on the rhs

      if (CS(rhs) || NS(rhs)) {
        // rhs: CS || NS
        // when rhs is a single value, possibly replace the outer or inner null
        // = union<rhs, list<union<nonnull<nonnull<lhs>.objtype>, rhs>>>
        return union([
          rhsTagged(rhs),
          list(
            union([
              lhsTagged(nonNullable(listObjectType(nonNullable(lhs)))),
              rhsTagged(rhs),
            ])
          ),
        ]);
      } else if (CLC(rhs) || CLN(rhs)) {
        // rhs: CLC || CLN
        // when rhs is a list of values, same as above, but with the object type
        // = union<rhs, list<union<nonnull<nonnull<lhs>.objtype>, rhs.objtype>>>
        return union([
          rhsTagged(rhs),
          list(
            union([
              lhsTagged(nonNullable(listObjectType(nonNullable(lhs)))),
              rhsTagged(listObjectType(rhs)),
            ])
          ),
        ]);
      } else if (NLC(rhs) || NLN(rhs)) {
        // rhs: NLC || NLN
        // very similar as the above
        // = union<rhs, list<union<nonnull<nonnull<lhs>.objtype>, nonnull<rhs>.objtype>>>
        return union([
          rhsTagged(rhs),
          list(
            maybe(
              union([
                lhsTagged(nonNullable(listObjectType(nonNullable(lhs)))),
                rhsTagged(listObjectType(nonNullable(rhs))),
              ])
            )
          ),
        ]);
      }
    }

    // This should never be the case
    return 'none';
  },
  resolver: async (inputs, forwardOp, forwardGraph, context) => {
    const lhs = getValueFromTaggedValue(inputs.lhs);
    const lhsTagged = (val: any) => {
      return isConcreteTaggedValue<'any', 'any'>(inputs.lhs)
        ? concreteTaggedValue(inputs.lhs._tag, val)
        : val;
    };
    const rhs = getValueFromTaggedValue(inputs.rhs);
    const rhsTagged = (val: any) => {
      return isConcreteTaggedValue<'any', 'any'>(inputs.rhs)
        ? concreteTaggedValue(inputs.rhs._tag, val)
        : val;
    };

    if (lhs == null) {
      if (rhs != null) {
        return rhsTagged(rhs);
      } else {
        return null;
      }
    } else if (rhs == null) {
      return lhsTagged(lhs);
    } else {
      if (_.isArray(lhs)) {
        if (_.isArray(rhs)) {
          const results: any[] = [];
          const length = max([lhs.length, rhs.length]) ?? 0;
          for (let i = 0; i < length; i++) {
            if (i < lhs.length) {
              if (lhs[i] == null) {
                if (i < rhs.length) {
                  results.push(rhsTagged(rhs[i]));
                } else {
                  results.push(null);
                }
              } else {
                results.push(lhsTagged(lhs[i]));
              }
            } else {
              // For now, we will not fill beyond the length of lhs
              // TODO: Incorporate this overflow into type system
              // if (i < rhs.length) {
              //   results.push(rhsTagged(rhs[i]));
              // } else {
              //   results.push(null);
              // }
            }
          }
          return results;
        } else {
          const results: any[] = [];
          lhs.forEach(item => {
            if (item == null) {
              results.push(rhsTagged(rhs));
            } else {
              results.push(lhsTagged(item));
            }
          });
          return results;
        }
      } else {
        return lhsTagged(lhs);
      }
    }
  },
});
