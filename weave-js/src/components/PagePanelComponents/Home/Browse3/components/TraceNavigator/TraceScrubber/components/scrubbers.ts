import {createScrubber} from './BaseScrubber';

export const TimelineScrubber = createScrubber({
  label: 'Timeline',
  description: 'Navigate through all calls in chronological order',
  alwaysEnabled: true,
  getNodes: ({traceTreeFlat}) =>
    Object.values(traceTreeFlat)
      .sort(
        (a, b) => Date.parse(a.call.started_at) - Date.parse(b.call.started_at)
      )
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
      .sort(
        (a, b) => Date.parse(a.call.started_at) - Date.parse(b.call.started_at)
      )
      .map(node => node.id);
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
        .sort(
          (a, b) =>
            Date.parse(a.call.started_at) - Date.parse(b.call.started_at)
        )
        .map(node => node.id);
    }

    return traceTreeFlat[parentId].childrenIds;
  },
});
