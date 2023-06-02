import {
  ConstNode,
  EditingNode,
  EditingOp,
  EditingOpInputs,
  EditingOutputNode,
  Frame,
  isBinaryOp,
  isBracketsOp,
  isConstNodeWithType,
  isDotChainedOp,
  isGetAttr,
  opDisplayName,
  opNeedsParens,
  OpStore,
  opSymbol,
} from '@wandb/weave/core';
import * as _ from 'lodash';
import * as React from 'react';

import {useWeaveContext} from '../../context';
import * as S from './ExpressionView.styles';

const ArgsView: React.FC<{
  args: EditingOpInputs;
}> = ({args}) => {
  // TODO: What to do if inputType is no longer valid for a step?
  const argNames = Object.keys(args);
  const argValues = Object.values(args);
  return (
    <>
      (
      {argValues.map((inNode, i) => (
        <span key={i}>
          {<NodeView node={inNode} />}
          {i < argNames.length - 1 && (
            <span style={{pointerEvents: 'none'}}>,&nbsp;</span>
          )}
        </span>
      ))}
      )
    </>
  );
};

const OpView: React.FC<{op: EditingOp}> = ({op}) => {
  const {client} = useWeaveContext();
  // TODO: What to do if inputType is no longer valid for a step?
  const expNode = useExpNode();
  const argNames = Object.keys(op.inputs);
  const argValues = Object.values(op.inputs);
  if (isBinaryOp(op, client.opStore)) {
    // Binary op
    const needsParens = opNeedsParens(op, expNode, client.opStore);
    return (
      <span>
        {needsParens && '('}
        <NodeView node={argValues[0]} /> {opSymbol(op, client.opStore)}{' '}
        <NodeView node={argValues[1]} />
        {needsParens && ')'}
      </span>
    );
  }

  if (isGetAttr(op, client.opStore)) {
    const obj = argValues[0];
    // If we're picking directly of a variable and we the key is a const,
    // just render the key itself with no quotes
    const key = argValues[1];
    if (obj.nodeType === 'var' && key.nodeType === 'const') {
      return <span>{key.val}</span>;
    }
    // Otherwise [] index notation
    return (
      <span>
        <NodeView node={argValues[0]} />
        .
        <NodeView node={argValues[1]} />
      </span>
    );
  }

  if (isBracketsOp(op, client.opStore)) {
    const obj = argValues[0];
    // If we're picking directly of a variable and we the key is a const,
    // just render the key itself with no quotes
    const key = argValues[1];
    if (obj.nodeType === 'var' && key.nodeType === 'const') {
      return <span>{key.val}</span>;
    }
    // Otherwise [] index notation
    return (
      <span>
        <NodeView node={argValues[0]} />
        [
        <NodeView node={argValues[1]} />]
      </span>
    );
  }

  if (isDotChainedOp(op, client.opStore)) {
    const obj = argValues[0];
    // Note, we skip rendering left hand side (obj.) when it is a
    // variable. So x.count is just count

    return (
      <span>
        {obj.nodeType !== 'var' && (
          <>
            <NodeView node={argValues[0]} />.
          </>
        )}
        {opDisplayName(op, client.opStore)}
        {argNames.length > 1 && (
          <ArgsView args={_.pickBy(op.inputs, (v, k) => k !== argNames[0])} />
        )}
      </span>
    );
  }
  // Render as function call
  return (
    <span>
      {opDisplayName(op, client.opStore)}
      <ArgsView args={op.inputs} />
    </span>
  );
};

const OutputNodeView: React.FC<{
  node: EditingOutputNode;
}> = ({node}) => {
  return <OpView op={node.fromOp} />;
};

const ConstNodeView: React.FC<{
  node: ConstNode;
}> = ({node}) => {
  return isConstNodeWithType(node, 'string') ? (
    <span>{`"${node.val}"`}</span>
  ) : isConstNodeWithType(node, 'number') ? (
    <span>{node.val.toString()}</span>
  ) : isConstNodeWithType(node, {
      type: 'function',
      inputTypes: {},
      outputType: 'any',
    }) ? (
    <ExpressionView node={node.val} />
  ) : isConstNodeWithType(node, 'none') ? (
    <span>None</span>
  ) : (
    <div>?</div>
  );
};

export const NodeView: React.FC<{
  node: EditingNode;
}> = ({node}) => {
  return (
    <S.ExpressionView>
      {node.nodeType === 'var' ? (
        node.varName
      ) : node.nodeType === 'output' ? (
        <OutputNodeView node={node} />
      ) : node.nodeType === 'const' ? (
        <ConstNodeView node={node} />
      ) : (
        <></>
      )}
    </S.ExpressionView>
  );
};

const ExpressionViewContext: React.Context<{
  exp?: EditingNode;
}> = React.createContext({});
function useExpNode() {
  const {exp} = React.useContext(ExpressionViewContext);

  if (!exp) {
    throw new Error('ExpressionViewContext uninitialized');
  }

  return exp;
}
export const ExpressionView: React.FC<{
  frame?: Frame;
  node: EditingNode;
}> = ({node}) => {
  return (
    <ExpressionViewContext.Provider value={{exp: node}}>
      <NodeView node={node} />
    </ExpressionViewContext.Provider>
  );
};

// These functions should produce the same result as ExpressionView

export const simpleArgsString = (
  args: EditingOpInputs,
  opStore: OpStore
): string =>
  '(' +
  Object.values(args)
    .map(v => simpleNodeString(v, opStore))
    .join(', ') +
  ')';

export const simpleOpString = (op: EditingOp, opStore: OpStore): string => {
  const argNames = Object.keys(op.inputs);
  const argValues = Object.values(op.inputs);
  if (isBinaryOp(op, opStore)) {
    return `${simpleNodeString(argValues[0], opStore)} ${opSymbol(
      op,
      opStore
    )} ${simpleNodeString(argValues[1], opStore)}`;
  }

  if (isBracketsOp(op, opStore)) {
    // Note, we skip rendering left hand side (obj.) when it is a
    // variable. So x.count is just count
    const obj = argValues[0];
    const key = argValues[1];
    if (obj.nodeType === 'var' && key.nodeType === 'const') {
      return key.val;
    }
    return `${simpleNodeString(obj, opStore)}[${simpleNodeString(
      key,
      opStore
    )}]`;
  }
  if (isDotChainedOp(op, opStore)) {
    // Note, we skip rendering left hand side (obj.) when it is a
    // variable. So x.count is just count
    const obj = argValues[0];
    const leftHandSide =
      obj.nodeType === 'var' ? '' : simpleNodeString(argValues[0], opStore);
    return `${leftHandSide}${opDisplayName(op, opStore)}${
      argNames.length > 1
        ? simpleArgsString(
            _.pickBy(op.inputs, (v, k) => k !== argNames[0]),
            opStore
          )
        : ''
    }`;
  }
  return `${opDisplayName(op, opStore)} ${simpleArgsString(
    op.inputs,
    opStore
  )} `;
};

export const simpleNodeString = (node: EditingNode, opStore: OpStore): string =>
  node.nodeType === 'var'
    ? node.varName
    : node.nodeType === 'output'
    ? simpleOpString(node.fromOp, opStore)
    : node.nodeType === 'const'
    ? node.type === 'number'
      ? node.val.toString()
      : node.type === 'string'
      ? node.val
      : '?'
    : '-';
