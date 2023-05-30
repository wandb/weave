import {
  defaultLanguageBinding,
  EditingNode,
  EditingOp,
  isEditingNode,
  NormGraph,
  OpStore,
} from '@wandb/weave/core';

type CytoGraph = any[];

export function normGraphToCyto(
  ng: NormGraph,
  opStore: OpStore,
  highlightNodeOrOp?: EditingNode | EditingOp
): CytoGraph {
  const cytoGraph: CytoGraph = [];

  for (const [op, opId] of ng.ops) {
    const engines = opStore.getOpDef(op.name).supportedEngines;
    const color =
      engines.size === 0
        ? '#000000'
        : engines.size === 1
        ? engines.has('py')
          ? '#f0ff00'
          : engines.has('ts')
          ? '#0000ff'
          : '#000000'
        : '#00ff00';
    const opClasses: string[] = [];
    const isConsumingOutputNode =
      highlightNodeOrOp &&
      isEditingNode(highlightNodeOrOp) &&
      highlightNodeOrOp?.nodeType === 'output' &&
      highlightNodeOrOp.fromOp === op;
    if (op === highlightNodeOrOp || isConsumingOutputNode) {
      opClasses.push('highlight');
    }
    cytoGraph.push({
      data: {id: opId, label: op.name, type: 'op'},
      style: {backgroundColor: color},
      classes: opClasses,
    });
    for (const argName of Object.keys(op.inputs)) {
      const argNode = op.inputs[argName];
      if (argNode.nodeType === 'output') {
        cytoGraph.push({
          data: {
            id: `${opId}-${argName}`,
            label: defaultLanguageBinding.printType(argNode.type),
            source: ng.ops.get(argNode.fromOp),
            target: opId,
          },
        });
      } else if (argNode.nodeType === 'const') {
        const nodeId = ng.constNodes.get(argNode);
        const classes = ['const'];
        if (highlightNodeOrOp === argNode) {
          classes.push('highlight');
        }
        cytoGraph.push({
          data: {id: nodeId, label: argNode.val, type: 'const'},
          classes,
        });
        cytoGraph.push({
          data: {
            id: `${opId}-${argName}`,
            label: defaultLanguageBinding.printType(argNode.type),
            source: nodeId,
            target: opId,
          },
        });
      } else if (argNode.nodeType === 'var') {
        const nodeId = ng.varNodes.get(argNode);
        const classes = ['var'];
        if (highlightNodeOrOp === argNode) {
          classes.push('highlight');
        }
        cytoGraph.push({
          data: {id: nodeId, label: argNode.varName, type: 'var'},
          classes,
        });
        cytoGraph.push({
          data: {
            id: `${opId}-${argName}`,
            label: defaultLanguageBinding.printType(argNode.type),
            source: nodeId,
            target: opId,
          },
        });
      } else if (argNode.nodeType === 'void') {
        const nodeId = ng.voidNodes.get(argNode);
        const classes = ['void'];
        if (highlightNodeOrOp === argNode) {
          classes.push('highlight');
        }
        cytoGraph.push({
          data: {id: nodeId, label: 'void', type: 'void'},
          classes,
        });
        cytoGraph.push({
          data: {
            id: `${opId}-${argName}`,
            source: nodeId,
            target: opId,
          },
        });
      }
    }
  }
  return cytoGraph;
}
