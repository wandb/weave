import {MOON_50} from '@wandb/weave/common/css/color.styles';
import {IconChevronDown} from '@wandb/weave/components/Icon';
import {
  constFunction,
  constNodeUnsafe,
  constString,
  isFunctionLiteral,
  Node,
  NodeOrVoidNode,
  opIndex,
  opPick,
  pickSuggestions,
  Type,
  varNode,
  voidNode,
  // opLimit,
} from '@wandb/weave/core';
import * as _ from 'lodash';
import React, {useCallback, useMemo} from 'react';

import {WeaveExpression} from '../../panel/WeaveExpression';
import {useMutation, useNodeValue} from '../../react';
import {ConfigFieldModifiedDropdown, ConfigFieldWrapper} from './ConfigPanel';
import * as Panel2 from './panel';
import {PanelContextProvider} from './PanelContext';
import {getSimpleKeyType, VisualEditorMode} from './visualEditors';

const inputType = {
  type: 'function' as const,
  inputTypes: {},
  outputType: 'any' as const,
};
interface PanelGroupingEditorConfig {
  node: Node;
}

type PanelGroupingEditorProps = Panel2.PanelProps<
  typeof inputType,
  PanelGroupingEditorConfig
>;

interface VisualGroupingState {
  key: string;
}

// GroupingEditor is a generic editor for filters, for any list.
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

const groupingExpressionToVisualState = (
  expr: NodeOrVoidNode
): VisualGroupingState | null => {
  if (expr.nodeType === 'void') {
    return null;
  }
  if (expr.nodeType !== 'output') {
    return null;
  }
  if (expr.fromOp.name !== 'pick') {
    return null;
  }
  if (expr.fromOp.inputs.key.nodeType !== 'const') {
    return null;
  }
  return {
    key: expr.fromOp.inputs.key.val as string,
  };
};

const visualGroupingStateToExpression = (
  groupingState: VisualGroupingState,
  listItemType: Type
) => {
  return opPick({
    obj: varNode(listItemType, 'row'),
    key: constString(groupingState.key),
  });
};

const setGroupingKey = (
  groupingState: VisualGroupingState,
  key: string
): VisualGroupingState => {
  return {
    key,
  };
};

export const PanelGroupingEditor: React.FC<
  PanelGroupingEditorProps
> = props => {
  const listItem = opIndex({
    arr: props.config!.node,
    index: varNode('number', 'n'),
  });
  const valueNode = props.input;
  const valueQuery = useNodeValue(valueNode, {callSite: 'PanelGroupingEditor'});
  const value = valueQuery.loading
    ? constFunction({}, () => voidNode() as any)
    : valueQuery.result;
  const setVal = useMutation(valueNode, 'set');
  const [mode, setMode] = React.useState<'visual' | 'expression'>('visual');

  const groupingState =
    value.nodeType === 'const'
      ? groupingExpressionToVisualState(value.val)
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

  const updateValFromVisualState = useCallback(
    (gs: VisualGroupingState) => {
      const newExpr = visualGroupingStateToExpression(gs, listItem.type);
      updateVal(newExpr);
    },
    [listItem.type, updateVal]
  );

  const paramVars = useMemo(
    () => _.mapValues(inputTypes, (type, name) => varNode(type, name)),
    [inputTypes]
  );

  const keyChoices = pickSuggestions(listItem.type)
    .filter(
      k =>
        getSimpleKeyType(opPick({obj: listItem, key: constString(k)}).type) ===
        'string'
    )
    .sort((a, b) => keySortOrder(a) - keySortOrder(b) || a.localeCompare(b));
  const keyOptions = keyChoices.map(k => ({text: k, value: k, k}));

  if (valueQuery.loading) {
    return <div>Loading...</div>;
  }

  return (
    <div style={{width: '100%', height: '100%', padding: '0 16px'}}>
      <VisualEditorMode
        mode={mode}
        visualAvailable={groupingState != null}
        setMode={setMode}
      />
      {mode === 'expression' || groupingState == null ? (
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
          <ConfigFieldWrapper withIcon>
            <ConfigFieldModifiedDropdown
              value={groupingState.key}
              onChange={(e, {value: v}) => {
                updateValFromVisualState(
                  setGroupingKey(groupingState, v as string)
                );
              }}
              options={keyOptions}
              floating
              icon={<IconChevronDown width={18} />}
            />
          </ConfigFieldWrapper>
        </div>
      )}
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  hidden: true,
  id: 'GroupingEditor',
  Component: PanelGroupingEditor,
  inputType,
};
