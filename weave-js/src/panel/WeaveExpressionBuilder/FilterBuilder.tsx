import {ConstructionOutlined} from '@mui/icons-material';
import {usePanelContext} from '@wandb/weave/components/Panel2/PanelContext';
import {useWeaveContext} from '@wandb/weave/context';
import {
  callOpVeryUnsafe,
  constBoolean,
  constNumber,
  constString,
  EditingNode,
  isAssignableTo,
  isNodeOrVoidNode,
  isOutputNode,
  isVarNode,
  isVoidNode,
  Node,
  OpDef,
  opPick,
  pickSuggestions,
  refineEditingNode,
  toFrame,
  varNode,
  voidNode,
} from '@wandb/weave/core';
import {nodeToString} from '@wandb/weave/core/language/js/print';
import React, {useCallback, useEffect, useRef, useState} from 'react';
import {Button, Dropdown, Icon, Portal} from 'semantic-ui-react';

import {useFilterBuilderState} from './hooks';
import {WeaveExpressionBuilderProps} from './types';
import * as S from './WeaveExpressionBuilder.style';

interface FilterRow {
  id: string;
  enabled: boolean;
  column: string;
  columnEditorString: string;
  operator: string;
  operatorEditorString: string;
  value: string;
  valueEditorString: string;
  valueType: string;
}

type FilterStep = 'column' | 'operator' | 'value';

interface FilterBuilderState {
  currentStep: FilterStep;
  currentFilterId: string;
  isWaitingForSuggestions: boolean;
  expression: string;
}

interface DropdownProps {
  key: string;
  text: string;
  value?: OpDef | EditingNode | string;
}

const operatorOptions = [
  {key: '=', text: '=', value: '='},
  {key: '!=', text: '!=', value: '!='},
  {key: '>', text: '>', value: '>'},
  {key: '<', text: '<', value: '<'},
  {key: '>=', text: '>=', value: '>='},
  {key: '<=', text: '<=', value: '<='},
];

export const FilterExpressionBuilder: React.FC<WeaveExpressionBuilderProps> = ({
  expr,
  setExpression,
  propsSetFilterFunction,
}) => {
  const weave = useWeaveContext();
  const {stack} = usePanelContext();
  const frame = toFrame(stack);
  const rowNode = frame['row'] ? varNode(frame['row'].type, 'row') : voidNode();
  const triggerRef = useRef<HTMLDivElement>(null);

  const {
    state,
    setColumn,
    setOperator,
    setValue,
    toggleFilterEnabled,
    addFilterRow,
    removeFilterRow,
    getAllFilterRows,
    combinedExpression,
    isReady,
    setRowOperators,
    setSearchQuery,
  } = useFilterBuilderState({
    rowNode,
    expr,
    weave,
    stack,
  });

  const [pendingExpr, setPendingExpr] = useState(expr);
  const [pendingOp, setPendingOp] = useState<OpDef | null>(null);
  const [opSuggestions, setOpSuggestions] = useState<DropdownProps[] | null>(
    null
  );
  const [inputSuggestions, setInputSuggestions] = useState<
    DropdownProps[] | null
  >(null);
  const [columnSuggestions, setColumnSuggestions] = useState<
    DropdownProps[] | null
  >(null);
  const [colValue, setColValue] = useState<string | null>(null);
  const [opValue, setOpValue] = useState<string | null>(null);
  const [rhsValue, setRhsValue] = useState<Node | null>(null);

  const [filterPosition, setFilterPosition] = useState({top: 0, left: 0});

  const filterRows = getAllFilterRows();
  console.log({filterRows});

  const [hasChanges, setHasChanges] = useState(false);

  const [builderState, setBuilderState] = useState<FilterBuilderState>({
    currentStep: 'column',
    currentFilterId: '0',
    isWaitingForSuggestions: false,
    expression: '',
  });

  useEffect(() => {
    if (isVoidNode(pendingExpr)) {
      const frame = toFrame(stack);
      const rowNode = varNode(frame['row'].type, 'row');
      console.log('found voidNode, setting', {rowNode});
      setPendingExpr(rowNode);
      return;
    }

    if (!pendingExpr) {
      return;
    }
    weave.suggestions(pendingExpr, voidNode(), stack).then(res => {
      const ops = res
        .filter(s => s.category === 'Ops')
        .map(s => {
          if (isOutputNode(s.newNodeOrOp)) {
            return weave.client.opStore.getOpDef(s.newNodeOrOp.fromOp.name);
          } else {
            throw Error('why would there be an output node without a name');
          }
        });

      setOpSuggestions(
        ops.map(o => ({
          key: o.name,
          text: o.renderInfo?.repr || o.name,
          value: o,
        }))
      );
    });
  }, [pendingExpr, stack, weave]);

  useEffect(() => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setFilterPosition({
        top: rect.bottom + window.scrollY + 4,
        left: rect.left + window.scrollX,
      });
    }
  }, []);

  useEffect(() => {}, [opSuggestions]);

  const handleColumnFocus = (filterId: string) => {};

  const handleOperatorFocus = (filterId: string) => {};

  const handleValueFocus = (filterId: string) => {};

  // Update the "Switch to advanced" link click handler
  const handleSwitchToAdvanced = () => {};
  // Update the footer link reference
  const FooterAdvancedLink = () => (
    <S.AdvancedLink onClick={handleSwitchToAdvanced}>
      Switch to advanced
    </S.AdvancedLink>
  );

  const handleOperatorSelect = (_: any, data: {value: OpDef}) => {
    setPendingOp(data.value);
    setOpValue(data.value.name);
  };

  const handleSearchChange = (_: any, {searchQuery}: {searchQuery: string}) => {
    // This function shouldn't be used directly anymore
    console.warn('handleSearchChange called directly');
  };

  const handleValueSelect = (
    event: React.MouseEvent<HTMLDivElement>,
    data: {value: string | boolean | undefined | number}
  ) => {
    console.log(event, data);
  };

  // Add a function to handle value input in FilterBuilder.tsx
  const handleValueInput = (
    e: React.KeyboardEvent<HTMLElement>,
    filterId: string
  ) => {
    if (e.key !== 'Enter') return;

    const filter = filterRows.find(f => f.id === filterId);
    if (!filter || !filter.opDef || !filter.lhsExpr || !filter.searchQuery)
      return;

    // Get the expected type for RHS from the opDef
    const opDef = filter.opDef;

    const [opDefLhsType, opDefRhsType] = Object.values(opDef.inputTypes);
    let rhsNode;
    const rhsAsString = constString(filter.searchQuery);
    const rhsAsNumber = constNumber(parseFloat(filter.searchQuery));
    let rhsAsBool;
    if (['true', 'false'].includes(filter.searchQuery.toLowerCase())) {
      rhsAsBool = constBoolean(filter.searchQuery.toLowerCase() === 'true');
    }

    for (const rhs of [rhsAsString, rhsAsNumber, rhsAsBool]) {
      if (rhs === undefined) {
        continue;
      }
      console.log(rhs, opDefRhsType);
      if (isAssignableTo(rhs.type, opDefRhsType)) {
        rhsNode = rhs;
      }
    }
    console.log('!!!!!!!!', {rhsNode});
    if (rhsNode) {
      setValue(filterId, rhsNode);
      console.log(rhsNode);
      setSearchQuery(filterId, '');
      setHasChanges(true);
    }
  };

  const handleAddFilter = () => {
    // Use the hook's addFilterRow method to add a new filter
    addFilterRow();

    // Update UI state if necessary
    setHasChanges(true);

    // Reset any selections for the new filter
    setColValue(null);
    setOpValue(null);
    setRhsValue(null);
  };

  const handleToggleFilter = (id: string) => {
    // Use the hook's toggleFilterEnabled method instead of manually updating filters
    toggleFilterEnabled(id);

    // Mark that changes have been made
    setHasChanges(true);
  };

  const handleApply = () => {
    console.log({combinedExpression});
    if (combinedExpression && !isVoidNode(combinedExpression)) {
      refineEditingNode(weave.client, combinedExpression, stack).then(res => {
        if (setExpression) {
          setExpression(res);
        }
        if (propsSetFilterFunction) {
          propsSetFilterFunction(res);
        }
      });
    }
  };

  const handleCancel = () => {
    // Get all current filter rows
    const currentFilterRows = getAllFilterRows();

    // Remove all filter rows except the first one
    currentFilterRows.forEach((row, index) => {
      if (index > 0) {
        removeFilterRow(row.id);
      } else if (row.enabled) {
        // Disable the first filter row if it's enabled
        toggleFilterEnabled(row.id);
      }
    });

    // Reset UI state
    setColValue(null);
    setOpValue(null);
    setRhsValue(null);
    setSearchQuery('0', '');
    setHasChanges(false);

    // If no filters exist, add one disabled filter
    if (currentFilterRows.length === 0) {
      addFilterRow();
      // The newly added filter is enabled by default, so disable it
      toggleFilterEnabled('0');
    }
  };

  // Create a function to fetch operators for a column
  const fetchOperatorsForColumn = useCallback(
    async (rowId: string, lhsExpr: Node) => {
      if (!lhsExpr) return;

      try {
        const suggestions = await weave.suggestions(lhsExpr, voidNode(), stack);

        const operators = suggestions
          .filter(s => s.category === 'Ops')
          .map(s => {
            if (isOutputNode(s.newNodeOrOp)) {
              return weave.client.opStore.getOpDef(s.newNodeOrOp.fromOp.name);
            }
            return null;
          })
          .filter(Boolean) as OpDef[];

        // Update the row's available operators
        setRowOperators(rowId, operators);
      } catch (err) {
        console.error('Error fetching operators:', err);
      }
    },
    [weave, stack, setRowOperators]
  );

  // Modify the column selection handler to fetch operators
  const handleColumnSelect = useCallback(
    (filterId: string, columnName: string) => {
      // Set the column in the state
      setColumn(filterId, columnName);

      // If we have a valid row node
      if (isVarNode(rowNode)) {
        // Create the expression for this column
        const lhsExpr = opPick({
          obj: rowNode,
          key: constString(columnName),
        });

        // Fetch operators for this expression
        fetchOperatorsForColumn(filterId, lhsExpr);
      }
    },
    [rowNode, setColumn, fetchOperatorsForColumn]
  );

  return (
    <>
      <div ref={triggerRef} style={{width: '100%'}} />
      <Portal open>
        <S.FilterContainer
          style={{top: filterPosition.top, left: filterPosition.left}}>
          {filterRows.map((filter, index) => (
            <S.FilterRow key={filter.id}>
              <S.FilterCheckbox
                checked={filter.enabled}
                onChange={() => handleToggleFilter(filter.id)}
              />
              <S.FilterContent disabled={!filter.enabled}>
                <S.ColumnSelector
                  placeholder="select column"
                  selection
                  options={state.columnKeys.map(col => ({
                    key: col,
                    text: col,
                    value: col,
                  }))}
                  fluid
                  search
                  value={filter.column}
                  onChange={(_, data: any) =>
                    handleColumnSelect(filter.id, data.value)
                  }
                  onFocus={() => {
                    if (!filter.enabled) {
                      handleToggleFilter(filter.id);
                    }
                    handleColumnFocus(filter.id);
                  }}
                />
                <S.OperatorSelector
                  selection
                  options={(filter.availableOperators || []).map(op => ({
                    key: op.name,
                    text: op.renderInfo?.repr ?? op.name, // Use type instead of repr
                    value: op,
                  }))}
                  value={filter.opDef}
                  onChange={(_, data: any) =>
                    setOperator(filter.id, data.value)
                  }
                  disabled={!filter.lhsExpr}
                />
                {filter.opDef &&
                  !(filter.opDef.renderInfo.type === 'unary') && (
                    <S.ValueInput
                      className="ui selection dropdown"
                      placeholder="Enter value or pick column"
                      search
                      searchQuery={filter.searchQuery}
                      onSearchChange={(_, data: any) =>
                        setSearchQuery(filter.id, data.searchQuery)
                      }
                      onChange={handleValueSelect}
                      onKeyDown={e => handleValueInput(e, filter.id)}
                      disabled={!filter.opDef}
                      value={
                        filter.rhsExpr ? nodeToString(filter.rhsExpr) : ''
                      }>
                      <Dropdown.Menu>
                        {filter.searchQuery && (
                          <>
                            <Dropdown.Header content="Scalar Input" />
                            <Dropdown.Item
                              text={filter.searchQuery}
                              style={{fontWeight: 'bold'}}
                              value={filter.searchQuery}
                            />
                          </>
                        )}
                        <Dropdown.Header content="Columns" />
                        {state.columnKeys.map(col => (
                          <Dropdown.Item
                            text={col}
                            key={col}
                            value={col}
                            onClick={(e, data) => {
                              console.log('Selected scalar:', data.value);
                            }}
                          />
                        ))}
                      </Dropdown.Menu>
                    </S.ValueInput>
                  )}
                {index > 0 && (
                  <Button
                    icon="trash"
                    size="mini"
                    onClick={() => removeFilterRow(filter.id)}
                    style={{marginLeft: 'auto'}}
                  />
                )}
              </S.FilterContent>
            </S.FilterRow>
          ))}

          <S.ButtonContainer>
            <S.AddFilterButton size="small" onClick={handleAddFilter}>
              <Icon name="plus" />
              New filter
            </S.AddFilterButton>
          </S.ButtonContainer>

          <S.FooterContainer>
            <FooterAdvancedLink />

            {hasChanges && (
              <S.ButtonGroup>
                <S.ActionButton primary size="small" onClick={handleApply}>
                  Apply
                </S.ActionButton>
                <S.ActionButton size="small" onClick={handleCancel}>
                  Cancel
                </S.ActionButton>
              </S.ButtonGroup>
            )}
          </S.FooterContainer>
        </S.FilterContainer>
      </Portal>
    </>
  );
};
