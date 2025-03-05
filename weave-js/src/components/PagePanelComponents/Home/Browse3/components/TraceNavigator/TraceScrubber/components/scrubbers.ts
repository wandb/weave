import {
  getSortedPeerPathCallIds,
  locateNodeForCallId,
} from '../../TraceViews/CodeView';
import {buildCodeMap} from '../../TraceViews/utils';
import {createScrubber} from './BaseScrubber';

export const TimelineScrubber = createScrubber({
  label: 'Timeline',
  description: 'Navigate through all calls in chronological order',
  alwaysEnabled: true,
  getNodes: ({traceTreeFlat}) =>
    Object.values(traceTreeFlat)
      .sort((a, b) => a.dfsOrder - b.dfsOrder)
      .map(node => node.id),
});

export const PeerScrubber = createScrubber({
  label: 'Peers',
  description:
    'Navigate through all calls with the same op as the selected call',
  getNodes: ({traceTreeFlat, selectedCallId}) => {
    if (!selectedCallId) {
      return [];
    }
    const currentNode = traceTreeFlat[selectedCallId];
    if (!currentNode) {
      return [];
    }

    return Object.values(traceTreeFlat)
      .filter(node => node.call.op_name === currentNode.call.op_name)
      .sort((a, b) => a.dfsOrder - b.dfsOrder)
      .map(node => node.id);
  },
});

export const CodePathScrubber = createScrubber({
  label: 'Path',
  description:
    'Navigate through all calls with the same code path as the selected call',
  getNodes: ({traceTreeFlat, selectedCallId}) => {
    if (!selectedCallId) {
      return [];
    }
    const currentNode = traceTreeFlat[selectedCallId];
    if (!currentNode) {
      return [];
    }

    const codeMap = buildCodeMap(traceTreeFlat);
    const codeNode = locateNodeForCallId(codeMap, selectedCallId);
    return getSortedPeerPathCallIds(codeNode, traceTreeFlat);
  },
});

export const SiblingScrubber = createScrubber({
  label: 'Siblings',
  description:
    'Navigate through calls that share the same parent as the selected call',
  getNodes: ({traceTreeFlat, selectedCallId}) => {
    if (!selectedCallId) {
      return [];
    }
    const currentNode = traceTreeFlat[selectedCallId];
    if (!currentNode) {
      return [];
    }
    const parentId = currentNode.parentId;

    if (!parentId) {
      return Object.values(traceTreeFlat)
        .filter(node => !node.parentId)
        .sort((a, b) => a.dfsOrder - b.dfsOrder)
        .map(node => node.id);
    }

    return traceTreeFlat[parentId].childrenIds;
  },
});

export const StackScrubber = createScrubber({
  label: 'Stack',
  description:
    'Navigate up and down the call stack from root to the selected call',
  getNodes: ({stack}) => {
    return stack;
  },
});
