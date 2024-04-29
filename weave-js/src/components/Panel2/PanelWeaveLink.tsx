// PanelWeaveLink makes clickable links that update the root expression.
//
// The "to" config field is a Weave expression Node. Think of it like an
// f-string. Any variables present in the "to" expression will be evaluated,
// and then passed into the "to" expression as consts.
//
// For example, if to is model(input) where input is a variable that represents
// PanelLink's input node, PanelLink will evaluate the input node, and pass
// the result in place of the variable. So if input evaluates to 'x', when clicked
// the root expression will change to model('x').

import {
  constNodeUnsafe,
  expressionVariables,
  Frame,
  NodeOrVoidNode,
  opDict,
  taggableValue,
  voidNode,
} from '@wandb/weave/core';
import * as _ from 'lodash';
import React, {useCallback, useMemo} from 'react';
import styled from 'styled-components';

import {useWeaveContext} from '../../context';
import * as CGReact from '../../react';
import {ChildPanel, ChildPanelFullConfig} from './ChildPanel';
import * as Panel2 from './panel';
import {usePanelContext} from './PanelContext';

interface WeaveLinkConfig {
  to: NodeOrVoidNode;
  vars: Frame;
}

const PANEL_WEAVE_LINK_DEFAULT_CONFIG: WeaveLinkConfig = {
  to: voidNode(),
  vars: {},
};

// Don't show up in any suggestions for now.
const inputType = 'any';

type PanelLabeledItemProps = Panel2.PanelProps<
  typeof inputType,
  WeaveLinkConfig
>;

export const WeaveLink = styled.div`
  width: 100%;
  height: 100%;
  cursor: pointer;
`;

export const PanelWeaveLink: React.FC<PanelLabeledItemProps> = props => {
  const config = props.config ?? PANEL_WEAVE_LINK_DEFAULT_CONFIG;
  const {input, updateInput} = props;
  const updateChildPanelConfig = useCallback(
    (newItemConfig: ChildPanelFullConfig) => {
      console.warn(
        'Attempt to update child panel config in PanelWeave link: not yet supported'
      );
    },
    []
  );
  const weave = useWeaveContext();
  const {frame: contextFrame} = usePanelContext();

  // We substitute existing variables first. Only variables declared specifically
  // for this panel are templated.
  const toExpr = useMemo(
    () => weave.callFunction(config.to, contextFrame),
    [config.to, contextFrame, weave]
  );

  const templateVars = useMemo(
    () => ({
      ...config.vars,
      // This 'input' key is by convention, written in panel_weavelink.py
      // : weave_internal.make_var_node(self.input_node.type, "input")
      input,
    }),
    [input, config.vars]
  );

  // Find all variables in to expression. These are used as template variables.
  const vars = useMemo(
    () =>
      _.fromPairs(
        _.uniqBy(expressionVariables(toExpr), v => v.varName).map(v => [
          v.varName,
          v,
        ])
      ),
    [toExpr]
  );
  const varDictNode = useMemo(() => opDict(vars as any), [vars]);

  const varDictNodeExpanded = weave.callFunction(varDictNode, templateVars);
  const varsResult = CGReact.useNodeValue(varDictNodeExpanded);

  const linkTo = useMemo(() => {
    if (varsResult.loading) {
      return voidNode();
    }
    // Pass the evaluated variable results back into the config.to expression
    // as const nodes.
    return weave.callFunction(
      toExpr,
      _.mapValues(varsResult.result, (v, k) =>
        constNodeUnsafe(taggableValue(vars[k].type), v)
      )
    );
  }, [toExpr, vars, varsResult.loading, varsResult.result, weave]);

  const onClickLink = useCallback(() => {
    if (updateInput != null && linkTo.nodeType !== 'void') {
      updateInput(linkTo as any);
    }
  }, [updateInput, linkTo]);
  return (
    <WeaveLink
      onClick={onClickLink}
      title={
        linkTo.nodeType !== 'void' ? weave.expToString(linkTo) : undefined
      }>
      <ChildPanel config={input} updateConfig={updateChildPanelConfig} />
    </WeaveLink>
  );
};

export const Spec: Panel2.PanelSpec = {
  hidden: true,
  id: 'weavelink',
  Component: PanelWeaveLink,
  inputType,
};
