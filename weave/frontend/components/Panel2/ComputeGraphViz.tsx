import * as globals from '@wandb/common/css/globals.styles';

import * as React from 'react';
import makeComp from '@wandb/common/util/profiler';
import * as CGTypes from '@wandb/cg/browser/types';
import * as GraphNorm from '@wandb/cg/browser/graphNorm';
import * as GraphCyto from './graphCyto';

import cytoscape from 'cytoscape';
import dagre from 'cytoscape-dagre';
import CytoscapeComponent from 'react-cytoscapejs';

cytoscape.use(dagre);

let renderCount = 0;

export const ComputeGraphViz: React.FC<{
  node: CGTypes.EditingNode;
  highlightNodeOrOp?: CGTypes.EditingNode | CGTypes.EditingOp;
  width: number;
  height: number;
}> = makeComp(
  props => {
    const {node, highlightNodeOrOp, width, height} = props;

    // Note: this does EXPENSIVE OPERATIONS on every render cycle!
    // Don't use this component in production as is!
    const ng = GraphNorm.graphNorm(node);
    const cytoGraph = GraphCyto.normGraphToCyto(ng, highlightNodeOrOp);
    // And we use renderCount as a key to force Cytoscape to rerender.
    renderCount++;

    return (
      <CytoscapeComponent
        key={renderCount}
        maxZoom={1.5}
        elements={cytoGraph}
        // If we set height to 100%, or try to use flex, the component starts
        // growing an infinite loop for some reason
        style={{width, height}}
        layout={
          {
            name: 'dagre',
            rankDir: 'LR',
            // rankSep: 10,
            spacingFactor: 0.7,
            nodeDimensionsIncludeLabels: true,
            // cytoscape types don't know about this type because it comes
            // from dagre
          } as any
        }
        stylesheet={[
          {
            selector: 'node[label]',
            style: {
              label: 'data(label)',
              'font-size': '12px',
              'text-wrap': 'ellipsis',
              'text-max-width': '300',
              'text-margin-y': -4,
            },
          },
          {
            selector: 'node',
            style: {
              color: globals.gray800,
              'background-color': 'white',
              'border-color': globals.primary,
              'border-width': 2,
              width: 20,
              height: 20,
            },
          },
          {
            selector: 'node.highlight',
            style: {
              'background-color': globals.primary,
            },
          },
          {
            selector: 'node.const',
            style: {
              shape: 'rectangle',
              width: 30,
              height: 10,
            },
          },
          {
            selector: 'node.var',
            style: {
              shape: 'diamond',
              width: 20,
              height: 20,
            },
          },
          {
            selector: 'node.void',
            style: {
              shape: 'triangle',
              width: 20,
              height: 20,
            },
          },
          {
            selector: 'edge[label]',
            style: {
              label: 'data(label)',
              color: '#888',
              'font-size': '12px',
              'text-wrap': 'ellipsis',
              'text-max-width': '300',
              'text-margin-y': 10,
            },
          },
          {
            selector: 'edge',
            style: {
              width: 2,
              'line-color': '#99ccdf',
              // opacity: 0.5,
              'curve-style': 'straight',
            },
          },
          {
            selector: 'edge',
            style: {
              'target-arrow-shape': 'triangle',
              'target-arrow-color': '#99ccdf',
              // 'arrow-opacity': 0.5,
            },
          },
        ]}
      />
    );
  },
  {id: 'ComputeGraphViz'}
);
