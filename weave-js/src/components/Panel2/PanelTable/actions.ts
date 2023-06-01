import {
  constBoolean,
  constNone,
  constNumber,
  constString,
  isVoidNode,
  maybe,
  NodeOrVoidNode,
  opAnd,
  opNot,
  opNumberEqual,
  opNumberNotEqual,
  opStringEqual,
  opStringNotEqual,
  WeaveInterface,
} from '@wandb/weave/core';

import {NodeAction} from '../../../actions';

export const TableActions = (
  weave: WeaveInterface,
  filterFn: NodeOrVoidNode,
  setFilterFn: (n: NodeOrVoidNode) => void
): NodeAction[] => {
  function isFilterableNode(n: NodeOrVoidNode) {
    return (
      weave.typeIsAssignableTo(n.type, maybe('string')) ||
      weave.typeIsAssignableTo(n.type, maybe('number')) ||
      weave.typeIsAssignableTo(n.type, maybe('boolean'))
    );
  }

  return [
    {
      name: 'Filter: Only this value',
      icon: 'filter',
      detail: async (n, stack) => {
        const value = await weave.client.query(
          weave.dereferenceAllVars(n, stack)
        );
        const prepend = isVoidNode(filterFn) ? '' : '...AND ';
        if (typeof value === 'boolean') {
          return `${prepend}${!value ? '!' : ''}${weave.expToString(n, null)}`;
        }
        return `${prepend}${weave.expToString(n, null)} == ${JSON.stringify(
          value
        )}`;
      },
      isAvailable: isFilterableNode,
      doAction: async (n, stack) => {
        const value = await weave.client.query(
          weave.dereferenceAllVars(n, stack)
        );
        let predicate: NodeOrVoidNode = constBoolean(true);
        if (weave.typeIsAssignableTo(n.type, maybe('boolean'))) {
          if (value) {
            predicate = n;
          } else {
            predicate = opNot({bool: n});
          }
        } else if (weave.typeIsAssignableTo(n.type, maybe('number'))) {
          predicate = opNumberEqual({
            lhs: n,
            rhs: value === null ? constNone() : constNumber(value),
          });
        } else if (weave.typeIsAssignableTo(n.type, maybe('string'))) {
          predicate = opStringEqual({
            lhs: n,
            rhs: value === null ? constNone() : constString(value),
          });
        }

        if (isVoidNode(filterFn)) {
          // No filter set, just set it
          setFilterFn(predicate);
        } else {
          // Filter is set, set filter to (oldFilter AND newFilter)
          setFilterFn(opAnd({lhs: filterFn, rhs: predicate}));
        }
      },
    },
    {
      name: 'Filter: Exclude this value',
      icon: 'filter',
      detail: async (n, stack) => {
        const value = await weave.client.query(
          weave.dereferenceAllVars(n, stack)
        );
        const prepend = isVoidNode(filterFn) ? '' : '...AND ';
        if (typeof value === 'boolean') {
          return `${prepend}${value ? '!' : ''}${weave.expToString(n, null)}`;
        }
        return `${prepend}${weave.expToString(n, null)} != ${JSON.stringify(
          value
        )}`;
      },
      isAvailable: isFilterableNode,
      doAction: async (n, stack) => {
        const value = await weave.client.query(
          weave.dereferenceAllVars(n, stack)
        );
        let predicate: NodeOrVoidNode = constBoolean(true);
        if (weave.typeIsAssignableTo(n.type, maybe('boolean'))) {
          if (!value) {
            predicate = n;
          } else {
            predicate = opNot({bool: n});
          }
        } else if (weave.typeIsAssignableTo(n.type, maybe('number'))) {
          predicate = opNumberNotEqual({
            lhs: n,
            rhs: value === null ? constNone() : constNumber(value),
          });
        } else if (weave.typeIsAssignableTo(n.type, maybe('string'))) {
          predicate = opStringNotEqual({
            lhs: n,
            rhs: value === null ? constNone() : constString(value),
          });
        }

        if (isVoidNode(filterFn)) {
          // No filter set, just set it
          setFilterFn(predicate);
        } else {
          // Filter is set, set filter to (oldFilter AND newFilter)
          setFilterFn(opAnd({lhs: filterFn, rhs: predicate}));
        }
      },
    },
  ];
};
