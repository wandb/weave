import * as GraphNorm from '@wandb/cg/browser/graphNorm';
import * as HL from '@wandb/cg/browser/hl';
import * as Types from '@wandb/cg/browser/model/types';
import * as CGTypes from '@wandb/cg/browser/types';

type CytoGraph = any[];

export function normGraphToCyto(
  ng: GraphNorm.NormGraph,
  highlightNodeOrOp?: CGTypes.EditingNode | CGTypes.EditingOp
): CytoGraph {
  const cytoGraph: CytoGraph = [];

  for (const [op, opId] of ng.ops) {
    const opClasses: string[] = [];
    const isConsumingOutputNode =
      highlightNodeOrOp &&
      HL.isEditingNode(highlightNodeOrOp) &&
      highlightNodeOrOp?.nodeType === 'output' &&
      highlightNodeOrOp.fromOp === op;
    if (op === highlightNodeOrOp || isConsumingOutputNode) {
      opClasses.push('highlight');
    }
    cytoGraph.push({
      data: {id: opId, label: op.name, type: 'op'},
      classes: opClasses,
    });
    for (const argName of Object.keys(op.inputs)) {
      const argNode = op.inputs[argName];
      if (argNode.nodeType === 'output') {
        cytoGraph.push({
          data: {
            id: `${opId}-${argName}`,
            label: Types.toString(argNode.type),
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
            label: Types.toString(argNode.type),
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
            label: Types.toString(argNode.type),
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
