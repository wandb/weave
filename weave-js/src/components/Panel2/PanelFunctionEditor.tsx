import {
  constFunction,
  ConstNode,
  constNodeUnsafe,
  FunctionTypeSpecific,
  isFunctionLiteral,
  Type,
  varNode,
  voidNode,
} from '@wandb/weave/core';
import * as _ from 'lodash';
import React, {useCallback, useMemo} from 'react';

import {WeaveExpression} from '../../panel/WeaveExpression';
import {useMutation, useNodeValue} from '../../react';
import * as Panel2 from './panel';
import {PanelContextProvider} from './PanelContext';

const inputType = {
  type: 'function' as const,
  inputTypes: {},
  outputType: 'any' as const,
};
interface PanelFunctionEditorConfig {
  expr: ConstNode<FunctionTypeSpecific<{[key: string]: Type}, 'any'>>;
}
type PanelFunctionEditorProps = Panel2.PanelProps<
  typeof inputType,
  PanelFunctionEditorConfig
>;

export const PanelFunctionEditor: React.FC<
  PanelFunctionEditorProps
> = props => {
  const valueNode = props.input;
  const valueQuery = useNodeValue(valueNode);
  const value = valueQuery.loading
    ? constFunction({}, () => voidNode() as any)
    : valueQuery.result;
  const setVal = useMutation(valueNode, 'set');

  if (!isFunctionLiteral(value)) {
    throw new Error('Expected function literal');
  }

  const inputTypes = value.type.inputTypes;

  const updateVal = useCallback(
    (newVal: any) => {
      console.log('SET VAL NEW VAL', newVal);
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

  const paramVars = useMemo(
    () => _.mapValues(inputTypes, (type, name) => varNode(type, name)),
    [inputTypes]
  );

  if (valueQuery.loading) {
    return <div>Loading...</div>;
  }

  return (
    <div style={{width: '100%', height: '100%'}}>
      <PanelContextProvider newVars={paramVars}>
        <WeaveExpression expr={value.val} setExpression={updateVal} noBox />
      </PanelContextProvider>
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  hidden: true,
  id: 'FunctionEditor',
  Component: PanelFunctionEditor,
  inputType,
};
