import ModifiedDropdown from '@wandb/weave/common/components/elements/ModifiedDropdown';
import NumberInput from '@wandb/weave/common/components/elements/NumberInput';
import {MOON_50} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import {Icon} from '@wandb/weave/components/Icon';
import {
  constBoolean,
  constFunction,
  constNodeUnsafe,
  constNumber,
  constString,
  isFunctionLiteral,
  Node,
  NodeOrVoidNode,
  opAnd,
  opBooleanEqual,
  opBooleanNotEqual,
  opIndex,
  opNumberEqual,
  opNumberGreater,
  opNumberGreaterEqual,
  opNumberLess,
  opNumberLessEqual,
  opNumberNotEqual,
  opOr,
  opPick,
  opStringEqual,
  opStringNotEqual,
  opUnique,
  pickSuggestions,
  Type,
  varNode,
  voidNode,
  // opLimit,
} from '@wandb/weave/core';
import * as _ from 'lodash';
import React, {useCallback, useMemo, useState} from 'react';
import {Popup} from 'semantic-ui-react';

import {WeaveExpression} from '../../panel/WeaveExpression';
import {useMutation, useNodeValue} from '../../react';
import * as Panel2 from './panel';
import {PanelContextProvider} from './PanelContext';
import {getSimpleKeyType, VisualEditorMode} from './visualEditors';

const inputType = {
  type: 'function' as const,
  inputTypes: {},
  outputType: 'any' as const,
};
interface PanelFilterEditorConfig {
  node: Node;
}

type PanelFilterEditorProps = Panel2.PanelProps<
  typeof inputType,
  PanelFilterEditorConfig
>;

interface VisualClauseString {
  key: string;
  simpleKeyType: 'string';
  op: '=' | '!=';
  value: string;
}

interface VisualClauseStringIn {
  key: string;
  simpleKeyType: 'string';
  op: 'in';
  value: string[];
}
interface VisualClauseBoolean {
  key: string;
  simpleKeyType: 'boolean';
  op: '=' | '!=';
  value: boolean;
}

interface VisualClauseNumber {
  key: string;
  simpleKeyType: 'number';
  op: '=' | '!=' | '<' | '<=' | '>' | '>=';
  value: number;
}

type VisualClause =
  | VisualClauseString
  | VisualClauseStringIn
  | VisualClauseBoolean
  | VisualClauseNumber;

interface VisualClauseWorkingState {
  key?: string | undefined;
  simpleKeyType?: 'number' | 'string' | 'boolean' | 'other';
  op?: string | undefined;
  value?: string | number | boolean | string[] | undefined;
}

const visualClauseIsValid = (
  clause: VisualClauseWorkingState
): clause is VisualClause => {
  if (clause.key == null || clause.op == null) {
    return false;
  }
  if (clause.simpleKeyType === 'number' && typeof clause.value !== 'number') {
    return false;
  }
  if (clause.simpleKeyType === 'string') {
    if (clause.op === 'in') {
      if (!Array.isArray(clause.value) || !clause.value.every(_.isString)) {
        return false;
      }
      if (clause.value.length === 0) {
        return false;
      }
    } else if (typeof clause.value !== 'string') {
      return false;
    }
  }
  if (clause.simpleKeyType === 'boolean' && typeof clause.value !== 'boolean') {
    return false;
  }
  return true;
};

const getOpChoices = (
  simpleKeyType: 'string' | 'number' | 'boolean' | 'other'
) => {
  return simpleKeyType === 'boolean'
    ? ['=', '!=']
    : simpleKeyType === 'string'
    ? ['=', '!=', 'in']
    : simpleKeyType === 'number'
    ? ['=', '!=', '<', '<=', '>', '>=']
    : [];
};

// FilterEditor is a generic editor for filters, for any list.
// But we hardcode a sort order for our monitoring Span type for now.
// In the future this could be controlled by a config parameter.
const keySortOrder = (key: string) => {
  if (key.startsWith('attributes.')) {
    return 1;
  }
  if (key.startsWith('summary.')) {
    return 2;
  }
  if (key === 'id' || key.includes('_id')) {
    return 4;
  }
  return 3;
};

const SingleFilterVisualEditor: React.FC<{
  listNode: Node;
  clause: VisualClause | VisualClauseWorkingState | null;
  onCancel: () => void;
  onOK: () => void;
  setTempClause: (clause: VisualClauseWorkingState) => void;
}> = ({listNode, clause, onCancel, onOK, setTempClause}) => {
  const defaultKey = clause?.key;
  const defaultOp = clause?.op;
  const defaultValue = clause?.value;

  const listItem = opIndex({
    arr: listNode,
    index: varNode('number', 'n'),
  });
  const keyChoices = pickSuggestions(listItem.type)
    .filter(
      k =>
        getSimpleKeyType(opPick({obj: listItem, key: constString(k)}).type) !==
        'other'
    )
    .sort((a, b) => keySortOrder(a) - keySortOrder(b) || a.localeCompare(b));
  const keyOptions = keyChoices.map(k => ({text: k, value: k, k}));

  const key = defaultKey ?? keyChoices[0];

  const simpleKeyType = getSimpleKeyType(
    opPick({
      obj: listItem,
      key: constString(key ?? ''),
    }).type
  );

  const opChoices = getOpChoices(simpleKeyType);
  const opOptions = opChoices.map(k => ({text: k, value: k, k}));

  const op = defaultOp ?? opChoices[0];
  const value = defaultValue;

  // const valueQuery =
  // TODO: opLimit is broken in weave python when we have an ArrowWeaveList...
  // I think because we don't have opUnique?
  //   key != null
  //     ? opLimit({
  //         arr: opUnique({
  //           arr: opPick({obj: listNode, key: constString(key)}),
  //         }),
  //         limit: constNumber(500),
  //       })
  //     : voidNode();
  const valueQuery =
    key != null && simpleKeyType === 'string'
      ? opUnique({
          arr: opPick({obj: listNode, key: constString(key)}),
        })
      : voidNode();
  const valueChoices = useNodeValue(valueQuery).result ?? [];
  const valueOptions = valueChoices
    .filter((v: any) => v != null)
    .map((v: boolean | string | number) => ({
      text: v.toString(),
      value: v,
      key: v.toString(),
    }));

  const curClause: VisualClauseWorkingState = useMemo(
    () => ({key, simpleKeyType, op, value}),
    [key, simpleKeyType, op, value]
  );
  const valid = visualClauseIsValid(curClause);
  const handleSetClause = useCallback(
    (partialClause: VisualClauseWorkingState) => {
      setTempClause({...curClause, ...partialClause});
    },
    [curClause, setTempClause]
  );

  return (
    <div style={{gap: '4px', display: 'flex', flexDirection: 'column'}}>
      <ModifiedDropdown
        value={key}
        onChange={(e, {value: k}) => {
          const newKey = k as string;
          const newSimpleKeyType = getSimpleKeyType(
            opPick({
              obj: listItem,
              key: constString(newKey),
            }).type
          );
          const newOpChoices = getOpChoices(newSimpleKeyType);
          handleSetClause({
            key: newKey,
            simpleKeyType: newSimpleKeyType,
            op: newOpChoices[0],
            value: undefined,
          });
        }}
        options={keyOptions}
        selection
      />
      <ModifiedDropdown
        value={op}
        onChange={(e, {value: v}) => {
          if (v === 'in') {
            if (op === '=' && typeof value === 'string') {
              handleSetClause({value: [value], op: v as string});
            } else {
              handleSetClause({value: [], op: v as string});
            }
          } else {
            handleSetClause({value: undefined, op: v as string});
          }
        }}
        options={opOptions}
        selection
      />
      {simpleKeyType === 'number' ? (
        <NumberInput
          value={value as number | undefined}
          onChange={newVal => {
            handleSetClause({value: newVal});
          }}
        />
      ) : (
        <ModifiedDropdown
          value={value}
          multiple={op === 'in'}
          onChange={(e, {value: v}) => {
            handleSetClause({value: v as VisualClauseWorkingState['value']});
          }}
          options={valueOptions}
          selection
        />
      )}
      <div
        style={{
          display: 'flex',
          gap: '8px',
          justifyContent: 'flex-end',
          marginTop: '4px',
        }}>
        <Button onClick={onCancel} variant="secondary">
          Cancel
        </Button>
        <Button
          disabled={!valid}
          onClick={() => {
            if (valid) {
              onOK();
            } else {
              // Shouldn't really happen since we filter above.
              onCancel();
            }
          }}>
          OK
        </Button>
      </div>
    </div>
  );
};

const clauseNodeToVisualStringIn = (
  clause: Node
): VisualClauseStringIn | null => {
  const inValues: string[] = [];
  let key: string | undefined;
  const addClauseValue = (node: Node) => {
    const singleClause = clauseNodeToVisual(node);
    if (singleClause == null) {
      return false;
    }
    if (singleClause.simpleKeyType !== 'string') {
      return false;
    }
    if (singleClause.op === 'in') {
      return false;
    }
    if (key == null) {
      key = singleClause.key;
    } else if (key !== singleClause.key) {
      return false;
    }
    inValues.push(singleClause.value);
    return true;
  };
  while (true) {
    if (clause.nodeType !== 'output') {
      return null;
    }
    const op = clause.fromOp;
    if (op.name === 'or') {
      if (!addClauseValue(op.inputs.rhs)) {
        return null;
      }
      clause = op.inputs.lhs;
    } else {
      if (!addClauseValue(clause)) {
        return null;
      }
      break;
    }
  }
  if (key == null) {
    return null;
  }
  return {
    key,
    simpleKeyType: 'string',
    op: 'in',
    value: inValues,
  };
};

const clauseNodeToVisual = (clause: Node): VisualClause | null => {
  if (clause.nodeType !== 'output') {
    return null;
  }
  const op = clause.fromOp;
  let opString;
  if (op.name === 'or') {
    return clauseNodeToVisualStringIn(clause);
  }
  if (['string-equal', 'boolean-equal', 'number-equal'].includes(op.name)) {
    opString = '=';
  } else if (
    ['string-notEqual', 'boolean-notEqual', 'number-notEqual'].includes(op.name)
  ) {
    opString = '!=';
  } else if (op.name === 'number-less') {
    opString = '<';
  } else if (op.name === 'number-lessEqual') {
    opString = '<=';
  } else if (op.name === 'number-greater') {
    opString = '>';
  } else if (op.name === 'number-greaterEqual') {
    opString = '>=';
  } else {
    return null;
  }
  const lhs = op.inputs.lhs;
  if (lhs.nodeType !== 'output') {
    return null;
  }
  if (lhs.fromOp.name !== 'pick') {
    return null;
  }
  const simpleKeyType = getSimpleKeyType(lhs.type);
  if (simpleKeyType === 'other') {
    return null;
  }
  if (lhs.fromOp.inputs.key.nodeType !== 'const') {
    return null;
  }
  const key = lhs.fromOp.inputs.key.val;
  const rhs = op.inputs.rhs;
  if (rhs.nodeType !== 'const') {
    return null;
  }
  const value = rhs.val;
  return {key, simpleKeyType, op: opString as any, value};
};

const filterExpressionToVisualClauses = (
  expr: NodeOrVoidNode
): VisualClause[] | null => {
  if (expr.nodeType === 'void') {
    return [];
  }
  if (expr.nodeType === 'const' && expr.val === true) {
    return [];
  }
  if (expr.nodeType !== 'output') {
    return null;
  }
  if (expr.fromOp.name !== 'and') {
    const singleVisualClause = clauseNodeToVisual(expr);
    if (singleVisualClause == null) {
      return null;
    }
    return [singleVisualClause];
  }
  const lhs = filterExpressionToVisualClauses(expr.fromOp.inputs.lhs);
  if (lhs == null) {
    return null;
  }
  const rhs = filterExpressionToVisualClauses(expr.fromOp.inputs.rhs);
  if (rhs == null) {
    return null;
  }
  return [...lhs, ...rhs];
};

const visualClausesToFilterExpression = (
  clauses: VisualClause[],
  listItemType: Type
) => {
  return clauses.reduce((expr, visualClause) => {
    const keyNode = opPick({
      obj: varNode(listItemType, 'row'),
      key: constString(visualClause.key),
    });
    let compOp;
    let valueNode;
    let clause;
    if (visualClause.op === 'in') {
      const val = visualClause.value as string[];
      if (val.length === 0) {
        return constNodeUnsafe('boolean', false);
      }
      clause = opStringEqual({
        lhs: keyNode,
        rhs: constString(val[0]),
      });
      for (let i = 1; i < val.length; i++) {
        const clauseI = opStringEqual({
          lhs: keyNode,
          rhs: constString(val[i]),
        });
        clause = opOr({
          lhs: clause,
          rhs: clauseI,
        });
      }
    } else {
      if (visualClause.simpleKeyType === 'string') {
        if (visualClause.op === '=') {
          compOp = opStringEqual;
        } else if (visualClause.op === '!=') {
          compOp = opStringNotEqual;
        }
        valueNode = constString(visualClause.value);
      } else if (visualClause.simpleKeyType === 'number') {
        if (visualClause.op === '=') {
          compOp = opNumberEqual;
        } else if (visualClause.op === '!=') {
          compOp = opNumberNotEqual;
        } else if (visualClause.op === '<') {
          compOp = opNumberLess;
        } else if (visualClause.op === '<=') {
          compOp = opNumberLessEqual;
        } else if (visualClause.op === '>') {
          compOp = opNumberGreater;
        } else if (visualClause.op === '>=') {
          compOp = opNumberGreaterEqual;
        }
        valueNode = constNumber(visualClause.value);
      } else if (visualClause.simpleKeyType === 'boolean') {
        if (visualClause.op === '=') {
          compOp = opBooleanEqual;
        } else if (visualClause.op === '!=') {
          compOp = opBooleanNotEqual;
        }
        valueNode = constBoolean(visualClause.value);
      }
      if (compOp == null) {
        throw new Error('Invalid visual clause');
      }
      clause = compOp({
        lhs: keyNode,
        rhs: valueNode as any,
      });
    }
    if (expr.nodeType === 'const' && expr.val === true) {
      return clause;
    }
    return opAnd({
      lhs: expr,
      rhs: clause,
    });
  }, constNodeUnsafe('boolean', true) as Node);
};

const addVisualClause = (
  clauses: VisualClause[],
  newClause: VisualClause
): VisualClause[] => {
  return [...clauses, newClause];
};

const setVisualClauseIndex = (
  clauses: VisualClause[],
  index: number,
  newClause: VisualClause
): VisualClause[] => {
  return [...clauses.slice(0, index), newClause, ...clauses.slice(index + 1)];
};

const removeVisualClause = (
  clauses: VisualClause[],
  index: number
): VisualClause[] => {
  return [...clauses.slice(0, index), ...clauses.slice(index + 1)];
};

const FilterPillBlock = (props: {
  clause: VisualClause;
  onClick: () => void;
  onRemove: () => void;
}) => {
  const {clause} = props;
  const valueStr = _.isArray(clause.value)
    ? clause.value.join(', ')
    : clause.value;
  return (
    <div
      style={{
        marginBottom: 4,
        display: 'flex',
        alignItems: 'center',
        backgroundColor: MOON_50,
        borderRadius: 8,
      }}>
      <Icon
        name="filter-alt"
        style={{
          margin: '0 8px',
        }}
      />
      <div
        style={{
          padding: '4px 8px 4px 0',
          cursor: 'pointer',
          textOverflow: 'ellipsis',
          overflow: 'hidden',
          whiteSpace: 'nowrap',
          width: '95%',
          lineHeight: '22px',
        }}
        onClick={props.onClick}>
        {`${clause.key} ${clause.op} ${valueStr}`}
      </div>
      <Icon
        name="close"
        onClick={props.onRemove}
        style={{
          margin: '0 8px',
          cursor: 'pointer',
        }}
      />
    </div>
  );
};

export const PanelFilterEditor: React.FC<PanelFilterEditorProps> = props => {
  const listItem = opIndex({
    arr: props.config!.node,
    index: varNode('number', 'n'),
  });
  const valueNode = props.input;
  const valueQuery = useNodeValue(valueNode, {callSite: 'PanelFilterEditor'});
  const value = valueQuery.loading
    ? constFunction({}, () => voidNode() as any)
    : valueQuery.result;
  const setVal = useMutation(valueNode, 'set');
  const [mode, setMode] = useState<'visual' | 'expression'>('visual');
  const [editingFilterIndex, setEditingFilterIndex] = useState<number | null>(
    null
  );
  const [editingFilter, setEditingFilter] =
    useState<VisualClauseWorkingState | null>(null);

  const visualClauses =
    value.nodeType === 'const'
      ? filterExpressionToVisualClauses(value.val)
      : null;

  if (!isFunctionLiteral(value)) {
    throw new Error('Expected function literal');
  }

  const inputTypes = value.type.inputTypes;
  const updateVal = useCallback(
    (newVal: any) => {
      // console.log('SET VAL NEW VAL', newVal);
      setVal({
        // Note we have to double wrap in Const here!
        // We are editing a Weave function with expression editor.
        // A weave function is Const(FunctionType(), Node). It must be
        // stored that way, we need FunctionType()'s input types to know
        // the input names and order for our function.
        // The first wrap with const node is to convert the Node edited
        // By WeaveExpression to our function format.
        // The second wrap is so that when the weave_api.set resolver runs
        // We still have our function format!
        val: constNodeUnsafe(
          'any',
          constNodeUnsafe(
            {
              type: 'function',
              inputTypes,
              outputType: newVal.type,
            },
            newVal
          )
        ),
      });
    },
    [setVal, inputTypes]
  );

  const updateValFromVisualClauses = useCallback(
    (clauses: VisualClause[]) => {
      const newExpr = visualClausesToFilterExpression(clauses, listItem.type);
      updateVal(newExpr);
    },
    [listItem.type, updateVal]
  );

  const resetEditedFilter = useCallback(() => {
    setEditingFilterIndex(null);
    setEditingFilter(null);
  }, [setEditingFilterIndex, setEditingFilter]);

  const commitEditedFilter = useCallback(() => {
    if (
      visualClauses &&
      editingFilter !== null &&
      visualClauseIsValid(editingFilter) &&
      editingFilterIndex != null
    ) {
      if (editingFilterIndex === -1) {
        updateValFromVisualClauses(
          addVisualClause(visualClauses, editingFilter)
        );
      } else if (!_.isEqual(editingFilter, visualClauses[editingFilterIndex])) {
        updateValFromVisualClauses(
          setVisualClauseIndex(visualClauses, editingFilterIndex, editingFilter)
        );
      }
    }
    setEditingFilterIndex(null);
    setEditingFilter(null);
  }, [
    editingFilter,
    editingFilterIndex,
    updateValFromVisualClauses,
    visualClauses,
  ]);

  const paramVars = useMemo(
    () => _.mapValues(inputTypes, (type, name) => varNode(type, name)),
    [inputTypes]
  );

  if (valueQuery.loading) {
    return <div>Loading...</div>;
  }

  return (
    <div style={{width: '100%', height: '100%', padding: '0 16px'}}>
      <VisualEditorMode
        mode={mode}
        visualAvailable={visualClauses != null}
        setMode={setMode}
      />
      {mode === 'expression' || visualClauses == null ? (
        <div
          style={{
            backgroundColor: MOON_50,
            padding: '4px 8px',
            borderRadius: '4px',
          }}>
          <PanelContextProvider newVars={paramVars}>
            <WeaveExpression expr={value.val} setExpression={updateVal} noBox />
          </PanelContextProvider>
        </div>
      ) : (
        <div>
          {visualClauses.map((clause, i) => (
            <Popup
              key={i}
              position="left center"
              popperModifiers={{
                preventOverflow: {
                  boundariesElement: 'offsetParent',
                },
              }}
              trigger={
                <FilterPillBlock
                  clause={clause}
                  onClick={() => setEditingFilterIndex(i)}
                  onRemove={() => {
                    updateValFromVisualClauses(
                      removeVisualClause(visualClauses, i)
                    );
                  }}
                />
              }
              on="click"
              onClose={commitEditedFilter}
              open={editingFilterIndex === i}
              content={
                <SingleFilterVisualEditor
                  listNode={props.config!.node}
                  clause={editingFilter ?? clause}
                  onCancel={resetEditedFilter}
                  onOK={commitEditedFilter}
                  setTempClause={setEditingFilter}
                />
              }
            />
          ))}
          <Popup
            position="left center"
            popperModifiers={{
              preventOverflow: {
                boundariesElement: 'offsetParent',
              },
            }}
            on="click"
            onClose={commitEditedFilter}
            open={editingFilterIndex === -1}
            trigger={
              <div>
                <Button
                  variant="ghost"
                  onClick={() => setEditingFilterIndex(-1)}>
                  + New filter
                </Button>
              </div>
            }
            content={
              <SingleFilterVisualEditor
                listNode={props.config!.node}
                clause={editingFilter || null}
                onCancel={resetEditedFilter}
                onOK={commitEditedFilter}
                setTempClause={setEditingFilter}
              />
            }
          />
        </div>
      )}
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  hidden: true,
  id: 'FilterEditor',
  icon: 'filter-alt',
  Component: PanelFilterEditor,
  inputType,
};
