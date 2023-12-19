import dagre from 'dagre';
import React, {useCallback, useMemo} from 'react';
import ReactFlow, {
  addEdge,
  ConnectionLineType,
  Edge as FlowEdge,
  Node as FlowNode,
  Position,
  useEdgesState,
  // Panel,
  useNodesState,
  useReactFlow,
  MarkerType,
} from 'react-flow-renderer';
import {useWeaveflowORMContext} from './wfInterface/context';
import {WFCall, WFObjectVersion} from './wfInterface/types';
import {CallLink, ObjectVersionLink} from './common/Links';

const nodeWidth = 130;
const nodeHeight = 40;

const getLayoutedElements = (
  nodes: FlowNode[],
  edges: FlowEdge[],
  direction = 'LR'
): {nodes: FlowNode[]; edges: FlowEdge[]; selectedNode?: FlowNode} => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  const isHorizontal = direction === 'LR';
  dagreGraph.setGraph({rankdir: direction});

  nodes.forEach(node => {
    dagreGraph.setNode(node.id, {width: nodeWidth, height: nodeHeight});
  });

  edges.forEach(edge => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  nodes.forEach(node => {
    const nodeWithPosition = dagreGraph.node(node.id);
    node.targetPosition = isHorizontal ? Position.Left : Position.Top;
    node.sourcePosition = isHorizontal ? Position.Right : Position.Bottom;

    // We are shifting the dagre node position (anchor=center center) to the top left
    // so it matches the React Flow node anchor point (top left).
    node.position = {
      x: nodeWithPosition.x - nodeWidth / 2,
      y: nodeWithPosition.y - nodeHeight / 2,
    };
    return node;
  });

  return {nodes, edges};
};

type FlowObjectsType = {
  nodes: FlowNode[];
  edges: FlowEdge[];
};

// const getAnsestorFlowObjectsForObjectVersion = (objectVersion: WFObjectVersion): FlowObjectsType => {
//     const nodes: FlowNode[] = []
//     const edges: FlowEdge[] = []

// }

const useFlowObjects = (objectVersion: WFObjectVersion): FlowObjectsType => {
  return useMemo(() => {
    const nodes: FlowNode[] = [];
    const edges: FlowEdge[] = [];

    // This is a very naive implementation of the DAG. We could get far more sophisticated
    // with this, but for now, we'll just do a simple traversal of the DAG.
    const ancestorObjectQueue: WFObjectVersion[] = [objectVersion];
    const ancestorCallQueue: WFCall[] = [];
    const visitedObjectVersions: Set<string> = new Set();
    const visitedCalls: Set<string> = new Set();

    while (ancestorObjectQueue.length > 0 || ancestorCallQueue.length > 0) {
      while (ancestorObjectQueue.length > 0) {
        const innerObjectVersion = ancestorObjectQueue.pop()!;
        if (visitedObjectVersions.has(innerObjectVersion.version())) {
          continue;
        }
        visitedObjectVersions.add(innerObjectVersion.version());
        nodes.push({
          id: innerObjectVersion.version(),
          data: {
            label: (
              <ObjectVersionLink
                entityName={innerObjectVersion.entity()}
                projectName={innerObjectVersion.project()}
                objectName={innerObjectVersion.object().name()}
                version={innerObjectVersion.version()}
              />
            ),
            objectVersion: innerObjectVersion,
          },
          position: {x: 0, y: 0},
          //   type: 'object',
        });
        innerObjectVersion.outputFrom().forEach(call => {
          ancestorCallQueue.push(call);
          edges.push({
            id: call.callID() + '->' + innerObjectVersion.version(),
            source: call.callID(),
            target: innerObjectVersion.version(),
            markerEnd: {
              type: MarkerType.Arrow,
            },
            animated: true,
          });
        });
      }
      while (ancestorCallQueue.length > 0) {
        const call = ancestorCallQueue.pop()!;
        if (visitedCalls.has(call.callID())) {
          continue;
        }
        visitedCalls.add(call.callID());
        nodes.push({
          id: call.callID(),
          data: {
            label: (
              <CallLink
                entityName={call.entity()}
                projectName={call.project()}
                callId={call.callID()}
              />
            ),
            call,
          },
          position: {x: 0, y: 0},
          //   type: 'call',
        });
        call.inputs().forEach(innerObjectVersion => {
          ancestorObjectQueue.push(innerObjectVersion);
          edges.push({
            id: innerObjectVersion.version() + '->' + call.callID(),
            source: innerObjectVersion.version(),
            target: call.callID(),
            markerEnd: {
              type: MarkerType.Arrow,
            },
            animated: true,
          });
        });
      }
    }

    // Child DAG tends to be enormous
    // const childObjectQueue: WFObjectVersion[] = [];
    // const childCallQueue: WFCall[] = [];

    // objectVersion.inputTo().forEach(call => {
    //   childCallQueue.push(call);
    //   edges.push({
    //     id: objectVersion.version() + '->' + call.callID(),
    //     source: objectVersion.version(),
    //     target: call.callID(),
    //   });
    // });

    // while (childObjectQueue.length > 0 || childCallQueue.length > 0) {
    //   while (childObjectQueue.length > 0) {
    //     const innerObjectVersion = childObjectQueue.pop()!;
    //     if (visitedObjectVersions.has(innerObjectVersion.version())) {
    //       continue;
    //     }
    //     visitedObjectVersions.add(innerObjectVersion.version());
    //     nodes.push({
    //       id: innerObjectVersion.version(),
    //       data: {
    //         innerObjectVersion,
    //       },
    //       position: {x: 0, y: 0},
    //     });
    //     innerObjectVersion.inputTo().forEach(call => {
    //       childCallQueue.push(call);
    //       edges.push({
    //         id: innerObjectVersion.version() + '->' + call.callID(),
    //         source: innerObjectVersion.version(),
    //         target: call.callID(),
    //       });
    //     });
    //   }
    //   while (childCallQueue.length > 0) {
    //     const call = childCallQueue.pop()!;
    //     if (visitedCalls.has(call.callID())) {
    //       continue;
    //     }
    //     visitedCalls.add(call.callID());
    //     nodes.push({
    //       id: call.callID(),
    //       data: {
    //         call,
    //       },
    //       position: {x: 0, y: 0},
    //     });
    //     call.output().forEach(innerObjectVersion => {
    //       childObjectQueue.push(innerObjectVersion);
    //       edges.push({
    //         id: call.callID() + '->' + innerObjectVersion.version(),
    //         source: call.callID(),
    //         target: innerObjectVersion.version(),
    //       });
    //     });
    //   }
    // }

    return {
      nodes,
      edges,
    };
  }, [objectVersion]);
};

const useLayedOutElements = (
  nodes: FlowNode[],
  edges: FlowEdge[]
): FlowObjectsType => {
  return useMemo(() => {
    return getLayoutedElements(nodes, edges);
  }, [edges, nodes]);
};

export const ObjectVersionPageDAG: React.FC<{
  objectVersion: WFObjectVersion;
}> = props => {
  //   const dagData = useDAGData();
  const {nodes, edges} = useFlowObjects(props.objectVersion);
  const {nodes: layoutedNodes, edges: layoutedEdges} = useLayedOutElements(
    nodes,
    edges
  );
  //   const {setCenter} = useReactFlow();
  return (
    <div style={{width: '100%', height: '100%'}}>
      <ReactFlow
        minZoom={0.1}
        nodes={layoutedNodes}
        edges={layoutedEdges}
        // nodeTypes={{
        //   object: ObjectNodeType,
        //   call: CallNodeType,
        // }}
        // onNodesChange={(events: any) => {
        //   let move = true;
        //   events.forEach((e: any) => {
        //     if (e.type === 'select') {
        //       move = false;
        //     }
        //   });
        //   if (move && selectedNode != null) {
        //     setCenter(selectedNode.position.x, selectedNode.position.y + 100, {
        //       zoom: 1,
        //       duration: 1000,
        //     });
        //   }
        // }}
        nodesDraggable={false}
        // onInit={() => {
        //   if (selectedNode != null) {
        //     setCenter(selectedNode.position.x, selectedNode.position.y + 100, {
        //       zoom: 1,
        //       duration: 1000,
        //     });
        //   }
        // }}
        onNodeClick={(event, node) => {
          console.log({event, node});
        }}
        connectionLineType={ConnectionLineType.Straight}
        fitView>
        {/* <Controls style={{marginBottom: '50px'}} /> */}
      </ReactFlow>
    </div>
  );
};

// const ObjectNodeType: React.FC = props => {
//   console.log(props);
//   return <div>{props.children}</div>;
// };
// const CallNodeType: React.FC = props => {
//   console.log(props);
//   return <div>{props.children}</div>;
// };
