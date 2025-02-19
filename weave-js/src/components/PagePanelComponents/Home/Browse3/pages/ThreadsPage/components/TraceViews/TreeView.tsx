import React, {useMemo} from 'react';

import {Button} from '../../../../../../../Button';
import {Icon, IconName} from '../../../../../../../Icon';
import {TraceViewProps} from '../../types';
import {formatDuration, formatTimestamp, getCallDisplayName} from './utils';

interface TreeNodeProps {
  id: string;
  call: any;
  childrenIds: string[];
  traceTreeFlat: TraceViewProps['traceTreeFlat'];
  selectedCallId?: string;
  onCallSelect: (id: string) => void;
  level?: number;
}

const TreeNode: React.FC<TreeNodeProps> = ({
  id,
  call,
  childrenIds,
  traceTreeFlat,
  selectedCallId,
  onCallSelect,
  level = 0,
}) => {
  const nodeRef = React.useRef<HTMLDivElement>(null);
  const [isExpanded, setIsExpanded] = React.useState(true);
  const hasChildren = childrenIds.length > 0;
  const duration = call.ended_at
    ? Date.parse(call.ended_at) - Date.parse(call.started_at)
    : Date.now() - Date.parse(call.started_at);

  const chevronIcon: IconName = isExpanded ? 'chevron-down' : 'chevron-next';

  // Scroll into view when selected
  React.useEffect(() => {
    let mounted = true;
    const doScroll = () => {
      if (mounted && id === selectedCallId && nodeRef.current) {
        nodeRef.current.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
        });
      }
    };

    const timeout = setTimeout(doScroll, 15);
    return () => {
      mounted = false;
      clearTimeout(timeout);
    };
  }, [id, selectedCallId]);

  return (
    <div className="flex flex-col">
      <span ref={nodeRef} >
      <Button
        variant={id === selectedCallId ? 'secondary' : 'ghost'}
        active={id === selectedCallId}
        onClick={() => onCallSelect(id)}
        className="w-full justify-start text-left">
        <div className="flex w-full items-center gap-2">
          <div style={{width: level * 20}} />
          {hasChildren && (
            <Icon
              name={chevronIcon}
              onClick={(e: React.MouseEvent) => {
                e.stopPropagation();
                setIsExpanded(!isExpanded);
              }}
              className="shrink-0 cursor-pointer"
            />
          )}
          {!hasChildren && <div className="w-4" />}
          <div className="flex flex-1 flex-col gap-1 overflow-hidden">
            <div className="truncate font-medium">
              {getCallDisplayName(call)}
            </div>
            <div className="truncate text-xs text-moon-500">
              Started: {formatTimestamp(call.started_at)}
              {call.ended_at && ` • Duration: ${formatDuration(duration)}`}
            </div>
          </div>
        </div>
      </Button>
      </span>
      {isExpanded && hasChildren && (
        <div className="flex flex-col">
          {childrenIds.map(childId => {
            const child = traceTreeFlat[childId];
            return (
              <TreeNode
                key={childId}
                id={childId}
                call={child.call}
                childrenIds={child.childrenIds}
                traceTreeFlat={traceTreeFlat}
                selectedCallId={selectedCallId}
                onCallSelect={onCallSelect}
                level={level + 1}
              />
            );
          })}
        </div>
      )}
    </div>
  );
};

export const TreeView: React.FC<TraceViewProps> = ({
  traceTreeFlat,
  selectedCallId,
  onCallSelect,
}) => {
  const rootNodes = useMemo(() => {
    return Object.values(traceTreeFlat).filter(
      node => !node.parentId || !traceTreeFlat[node.parentId]
    );
  }, [traceTreeFlat]);

  return (
    <div className="h-full overflow-hidden">
      <div className="h-[100%] overflow-y-auto p-4">
        <div className="flex flex-col gap-2">
          {rootNodes.map(node => (
            <TreeNode
              key={node.id}
              id={node.id}
              call={node.call}
              childrenIds={node.childrenIds}
              traceTreeFlat={traceTreeFlat}
              selectedCallId={selectedCallId}
              onCallSelect={onCallSelect}
            />
          ))}
        </div>
      </div>
    </div>
  );
};
