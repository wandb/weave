import * as S from './ExpressionView.styles';

import * as _ from 'lodash';
import * as React from 'react';
import makeComp from '@wandb/common/util/profiler';
import * as CG from '@wandb/cg/browser/graph';
import * as HL from '@wandb/cg/browser/hl';
import * as Code from '@wandb/cg/browser/code';
import * as Types from '@wandb/cg/browser/model/types';
import * as CGTypes from '@wandb/cg/browser/types';

const ArgsView: React.FC<{
  args: CGTypes.EditingOpInputs;
}> = makeComp(
  // TODO: What to do if inputType is no longer valid for a step?
  ({args}) => {
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
  },
  {id: 'ArgView'}
);

const OpView: React.FC<{op: CGTypes.EditingOp}> = makeComp(
  // TODO: What to do if inputType is no longer valid for a step?
  ({op}) => {
    const expNode = useExpNode();
    const argNames = Object.keys(op.inputs);
    const argValues = Object.values(op.inputs);
    if (HL.isBinaryOp(op)) {
      // Binary op
      const needsParens = HL.opNeedsParens(op, expNode);
      return (
        <span>
          {needsParens && '('}
          <NodeView node={argValues[0]} /> {HL.binaryOpSymbol(op)}{' '}
          <NodeView node={argValues[1]} />
          {needsParens && ')'}
        </span>
      );
    }

    if (HL.isBracketsOp(op)) {
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

    if (HL.isDotChainedOp(op)) {
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
          {HL.opDisplayName(op)}
          {argNames.length > 1 && (
            <ArgsView args={_.pickBy(op.inputs, (v, k) => k !== argNames[0])} />
          )}
        </span>
      );
    }
    // Render as function call
    return (
      <span>
        {HL.opDisplayName(op)}
        <ArgsView args={op.inputs} />
      </span>
    );
  },
  {id: 'OpView'}
);

const OutputNodeView: React.FC<{
  node: CGTypes.EditingOutputNode;
}> = makeComp(
  ({node}) => {
    return <OpView op={node.fromOp} />;
  },
  {id: 'OutputNodeView'}
);

const ConstNodeView: React.FC<{
  node: Types.ConstNode;
}> = makeComp(
  ({node}) => {
    return CG.constNodeIsType(node, 'string') ? (
      <span>{`"${node.val}"`}</span>
    ) : CG.constNodeIsType(node, 'number') ? (
      <span>{node.val.toString()}</span>
    ) : CG.constNodeIsType(node, {
        type: 'function',
        inputTypes: {},
        outputType: 'any',
      }) ? (
      <ExpressionView node={node.val} />
    ) : CG.constNodeIsType(node, 'none') ? (
      <span>None</span>
    ) : (
      <div>?</div>
    );
  },
  {id: 'ConstNodeView'}
);

export const NodeView: React.FC<{
  node: CGTypes.EditingNode;
}> = makeComp(
  ({node}) => {
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
  },
  {id: 'NodeView'}
);

const ExpressionViewContext: React.Context<{
  exp?: CGTypes.EditingNode;
}> = React.createContext({});
function useExpNode() {
  const {exp} = React.useContext(ExpressionViewContext);

  if (!exp) {
    throw new Error('ExpressionViewContext uninitialized');
  }

  return exp;
}
export const ExpressionView: React.FC<{
  frame?: Code.Frame;
  node: CGTypes.EditingNode;
}> = makeComp(
  ({node}) => {
    return (
      <ExpressionViewContext.Provider value={{exp: node}}>
        <NodeView node={node} />
      </ExpressionViewContext.Provider>
    );
  },
  {id: 'ExpressionViewContainer'}
);

// These functions should produce the same result as ExpressionView

export const simpleArgsString = (args: CGTypes.EditingOpInputs): string =>
  '(' +
  Object.values(args)
    .map(v => simpleNodeString(v))
    .join(', ') +
  ')';

export const simpleOpString = (op: CGTypes.EditingOp): string => {
  const argNames = Object.keys(op.inputs);
  const argValues = Object.values(op.inputs);
  if (HL.isBinaryOp(op)) {
    return `${simpleNodeString(argValues[0])} ${HL.binaryOpSymbol(
      op
    )} ${simpleNodeString(argValues[1])}`;
  }

  if (HL.isBracketsOp(op)) {
    // Note, we skip rendering left hand side (obj.) when it is a
    // variable. So x.count is just count
    const obj = argValues[0];
    const key = argValues[1];
    if (obj.nodeType === 'var' && key.nodeType === 'const') {
      return key.val;
    }
    return `${simpleNodeString(obj)}[${simpleNodeString(key)}]`;
  }
  if (HL.isDotChainedOp(op)) {
    // Note, we skip rendering left hand side (obj.) when it is a
    // variable. So x.count is just count
    const obj = argValues[0];
    const leftHandSide =
      obj.nodeType === 'var' ? '' : simpleNodeString(argValues[0]);
    return `${leftHandSide}${HL.opDisplayName(op)}${
      argNames.length > 1
        ? simpleArgsString(_.pickBy(op.inputs, (v, k) => k !== argNames[0]))
        : ''
    }`;
  }
  return `${HL.opDisplayName(op)} ${simpleArgsString(op.inputs)} `;
};

export const simpleNodeString = (node: CGTypes.EditingNode): string =>
  node.nodeType === 'var'
    ? node.varName
    : node.nodeType === 'output'
    ? simpleOpString(node.fromOp)
    : node.nodeType === 'const'
    ? node.type === 'number'
      ? node.val.toString()
      : node.type === 'string'
      ? node.val
      : '?'
    : '-';
