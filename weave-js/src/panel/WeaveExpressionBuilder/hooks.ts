import {
  callOpVeryUnsafe,
  constString,
  EditingNode,
  isEditingNode,
  isOutputNode,
  isVarNode,
  isVoidNode,
  Node,
  NodeOrVoidNode,
  OpDef,
  opPick,
  pickSuggestions,
  Stack,
  toFrame,
  VarNode,
  varNode,
  VoidNode,
  voidNode,
} from '@wandb/weave/core';
import {useCallback, useEffect, useState} from 'react';

export interface FilterBuilderRowState {
  id: string;
  enabled: boolean;
  lhsExpr: Node | null;
  opDef: OpDef | null;
  rhsExpr: Node | null;
  pendingExpr: EditingNode | null;
  column: string;
  availableOperators: OpDef[];
  searchQuery: string;
}

export interface FilterBuilderState {
  filterRowsState: {[id: string]: FilterBuilderRowState};
  columnKeys: string[];
  rowNode: VarNode | VoidNode | null;
  combinedPendingExpr: EditingNode | null;
  isReady: boolean;
}

export const useFilterBuilderState = ({
  rowNode,
  expr,
  weave,
  stack,
}: {
  rowNode: VarNode | VoidNode;
  expr: EditingNode | VoidNode;
  weave?: any;
  stack?: Stack;
}) => {
  console.log({expr});
  // Check if rowNode is void and handle appropriately
  const isVoidRowNode = isVoidNode(rowNode);

  // Only try to get column keys if rowNode is not void
  const columnKeys = !isVoidRowNode
    ? (pickSuggestions(rowNode.type) as string[])
    : [];

  const [state, setState] = useState<FilterBuilderState>({
    filterRowsState: {
      '0': {
        id: '0',
        enabled: false,
        lhsExpr: null,
        opDef: null,
        rhsExpr: null,
        pendingExpr: null,
        column: '',
        availableOperators: [],
        searchQuery: '',
      },
    },
    columnKeys,
    rowNode: isVarNode(rowNode) ? rowNode : null,
    combinedPendingExpr: voidNode() as EditingNode,
    isReady: !isVoidRowNode,
  });

  // Function to initialize state from an existing expression
  const initializeFromExpr = useCallback(
    (expression: NodeOrVoidNode) => {
      if (isVoidNode(expression)) {
        return; // Nothing to initialize
      }

      const newFilterRows: {[id: string]: FilterBuilderRowState} = {};
      let nextRowId = 0;

      // Recursive function to process expression tree
      const processExpr = (node: NodeOrVoidNode): void => {
        if (isVoidNode(node) || !isOutputNode(node) || !node.fromOp) {
          return;
        }

        const opName = node.fromOp.name;
        const inputs = node.fromOp.inputs;

        // Handle AND operations (multiple filters)
        if (opName === 'and') {
          if (inputs.lhs) processExpr(inputs.lhs);
          if (inputs.rhs) processExpr(inputs.rhs);
          return;
        }

        // Handle comparison operators (single filter)
        if (inputs.lhs && inputs.rhs) {
          let column = '';
          let lhsExpr = null;

          // Extract the column name from pick operation
          if (
            isOutputNode(inputs.lhs) &&
            inputs.lhs.fromOp &&
            inputs.lhs.fromOp.name === 'pick'
          ) {
            const pickInputs = inputs.lhs.fromOp.inputs;
            if (pickInputs.key && pickInputs.key.nodeType === 'const') {
              column = pickInputs.key.val;
              lhsExpr = inputs.lhs;
            }
          }

          // Create a new filter row
          const rowId = (nextRowId++).toString();

          // Get the operator definition if weave is available
          let opDef = null;
          if (weave && weave.client && weave.client.opStore) {
            opDef = weave.client.opStore.getOpDef(opName);
          }
          console.log(inputs.rhs);

          newFilterRows[rowId] = {
            id: rowId,
            enabled: true,
            column,
            lhsExpr,
            opDef,
            rhsExpr: inputs.rhs,
            pendingExpr: isEditingNode(node) ? node : null,
            availableOperators: [],
            searchQuery: inputs.rhs ? inputs.rhs.val : '',
          };
        }
      };

      // Start processing from the root expression
      processExpr(expression);

      // Update state with all processed filter rows, or create a default empty one
      if (Object.keys(newFilterRows).length > 0) {
        setState(prevState => ({
          ...prevState,
          filterRowsState: newFilterRows,
          combinedPendingExpr: isEditingNode(expression) ? expression : null,
        }));
      }

      return newFilterRows;
    },
    [weave]
  );

  // Initialize from expression on mount
  useEffect(() => {
    if (
      !isVoidNode(expr) &&
      Object.keys(state.filterRowsState).length === 1 &&
      !state.filterRowsState['0'].enabled
    ) {
      const newRows = initializeFromExpr(expr);

      // Fetch operators for each row if weave is available
      if (weave && stack && newRows) {
        Object.entries(newRows).forEach(([rowId, row]) => {
          if (row.lhsExpr) {
            fetchOperatorsForLhsExpr(rowId, row.lhsExpr);
          }
        });
      }
    }
  }, [expr, weave, stack, initializeFromExpr]);

  // Fetch operators for a lhs expression
  const fetchOperatorsForLhsExpr = useCallback(
    async (rowId: string, lhsExpr: Node) => {
      if (!weave || !stack) return;

      try {
        const suggestions = await weave.suggestions(lhsExpr, voidNode(), stack);

        const operators = suggestions
          .filter((s: any) => s.category === 'Ops')
          .map((s: any) => {
            if (isOutputNode(s.newNodeOrOp)) {
              return weave.client.opStore.getOpDef(s.newNodeOrOp.fromOp.name);
            }
            return null;
          })
          .filter(Boolean);

        // Filter for boolean-returning operations
        const booleanOps = operators.filter((op: OpDef) => {
          // Common comparison operators that return boolean
          const booleanOpNames = [
            'equal',
            'notEqual',
            'greaterThan',
            'lessThan',
            'greaterEqual',
            'lessEqual',
            'string-equal',
            'string-notEqual',
            'contains',
            'startsWith',
            'endsWith',
            'number-equal',
            'number-notEqual',
            'number-greater',
            'number-less',
            'number-greaterEqual',
            'number-lessEqual',
          ];

          // Check if the operation name matches known boolean ops
          return (
            booleanOpNames.some(name => op.name.includes(name)) ||
            // Check for returnType.type if the property exists
            (op as any).returnType?.type === 'boolean'
          );
        });

        setRowOperators(rowId, booleanOps);
      } catch (err) {
        console.error('Error fetching operators:', err);
      }
    },
    [weave, stack]
  );

  // Set column for a specific filter row
  const setColumn = useCallback(
    (rowId: string, column: string) => {
      setState(prevState => {
        // Don't proceed if rowNode is void
        if (isVoidRowNode || !isVarNode(rowNode)) return prevState;

        const row = prevState.filterRowsState[rowId];
        if (!row) return prevState;

        const lhsExpr = opPick({
          obj: rowNode,
          key: constString(column),
        });

        // Create updated row first (without operators)
        const updatedRow = {
          ...row,
          column,
          lhsExpr,
          pendingExpr: lhsExpr as EditingNode,
        };

        // Return immediately with the updated state (operators will be fetched asynchronously)
        return {
          ...prevState,
          filterRowsState: {
            ...prevState.filterRowsState,
            [rowId]: updatedRow,
          },
        };
      });

      // Fetch operators asynchronously for this specific row
      if (!isVoidRowNode && isVarNode(rowNode) && weave && stack) {
        const lhsExpr = opPick({
          obj: rowNode,
          key: constString(column),
        });

        fetchOperatorsForLhsExpr(rowId, lhsExpr);
      }
    },
    [rowNode, isVoidRowNode, weave, stack, fetchOperatorsForLhsExpr]
  );

  // Set operator for a specific filter row
  const setOperator = useCallback((rowId: string, opDef: OpDef) => {
    setState(prevState => {
      const row = prevState.filterRowsState[rowId];
      if (!row || !row.lhsExpr) return prevState;

      return {
        ...prevState,
        filterRowsState: {
          ...prevState.filterRowsState,
          [rowId]: {
            ...row,
            opDef,
          },
        },
      };
    });
  }, []);

  // Set value for a specific filter row
  const setValue = useCallback((rowId: string, value: Node) => {
    setState(prevState => {
      const row = prevState.filterRowsState[rowId];
      if (!row || !row.lhsExpr || !row.opDef) return prevState;

      const rhsExpr = value;
      const pendingExpr = callOpVeryUnsafe(row.opDef.name, {
        lhs: row.lhsExpr,
        rhs: rhsExpr,
      });

      return {
        ...prevState,
        filterRowsState: {
          ...prevState.filterRowsState,
          [rowId]: {
            ...row,
            rhsExpr,
            pendingExpr,
          },
        },
      };
    });

    // Recalculate combined expression whenever a value changes
    updateCombinedExpression();
  }, []);

  // Toggle a filter row enabled/disabled
  const toggleFilterEnabled = useCallback((rowId: string) => {
    setState(prevState => {
      const row = prevState.filterRowsState[rowId];
      if (!row) return prevState;

      return {
        ...prevState,
        filterRowsState: {
          ...prevState.filterRowsState,
          [rowId]: {
            ...row,
            enabled: !row.enabled,
          },
        },
      };
    });

    // Recalculate combined expression after toggling
    updateCombinedExpression();
  }, []);

  // Add a new filter row
  const addFilterRow = useCallback(() => {
    setState(prevState => {
      const newId = Object.keys(prevState.filterRowsState).length.toString();

      return {
        ...prevState,
        filterRowsState: {
          ...prevState.filterRowsState,
          [newId]: {
            id: newId,
            enabled: true,
            lhsExpr: null,
            opDef: null,
            rhsExpr: null,
            pendingExpr: null,
            column: '',
            availableOperators: [],
            searchQuery: '',
          },
        },
      };
    });
  }, []);

  // Recalculate the combined expression from all enabled filters
  const updateCombinedExpression = useCallback(() => {
    setState(prevState => {
      const enabledFilters = Object.values(prevState.filterRowsState).filter(
        row => row.enabled && row.pendingExpr
      );

      if (enabledFilters.length === 0) {
        return {
          ...prevState,
          combinedPendingExpr: voidNode() as EditingNode,
        };
      }

      // Use the first filter's expression
      let combinedExpr = enabledFilters[0].pendingExpr;

      // Combine additional filters with AND operations
      for (let i = 1; i < enabledFilters.length; i++) {
        if (enabledFilters[i].pendingExpr && combinedExpr) {
          combinedExpr = callOpVeryUnsafe('and', {
            lhs: combinedExpr,
            rhs: enabledFilters[i].pendingExpr!,
          });
        }
      }

      return {
        ...prevState,
        combinedPendingExpr: combinedExpr,
      };
    });
  }, []);

  // Remove a filter row
  const removeFilterRow = useCallback(
    (rowId: string) => {
      setState(prevState => {
        const newFilterRowsState = {...prevState.filterRowsState};
        delete newFilterRowsState[rowId];

        return {
          ...prevState,
          filterRowsState: newFilterRowsState,
        };
      });

      // Recalculate combined expression after removing a row
      updateCombinedExpression();
    },
    [updateCombinedExpression]
  );

  // Get a specific filter row
  const getFilterRow = useCallback(
    (rowId: string) => {
      return state.filterRowsState[rowId] || null;
    },
    [state.filterRowsState]
  );

  // Get all filter rows as an array
  const getAllFilterRows = useCallback(() => {
    return Object.values(state.filterRowsState);
  }, [state.filterRowsState]);

  // Add a function to set the available operators for a row
  const setRowOperators = useCallback((rowId: string, operators: OpDef[]) => {
    setState(prevState => {
      const row = prevState.filterRowsState[rowId];
      if (!row) return prevState;

      return {
        ...prevState,
        filterRowsState: {
          ...prevState.filterRowsState,
          [rowId]: {
            ...row,
            availableOperators: operators.filter(
              opDef => Object.keys(opDef.inputTypes).length <= 2
            ),
          },
        },
      };
    });
  }, []);

  const setSearchQuery = useCallback((rowId: string, query: string) => {
    setState(prevState => {
      const row = prevState.filterRowsState[rowId];
      if (!row) return prevState;

      return {
        ...prevState,
        filterRowsState: {
          ...prevState.filterRowsState,
          [rowId]: {
            ...row,
            searchQuery: query,
          },
        },
      };
    });
  }, []);

  return {
    state,
    setColumn,
    setOperator,
    setValue,
    toggleFilterEnabled,
    addFilterRow,
    removeFilterRow,
    getFilterRow,
    getAllFilterRows,
    combinedExpression: state.combinedPendingExpr,
    isReady: !isVoidRowNode, // Flag to indicate if filter builder can be used
    setRowOperators,
    setSearchQuery,
    initializeFromExpr,
  };
};
