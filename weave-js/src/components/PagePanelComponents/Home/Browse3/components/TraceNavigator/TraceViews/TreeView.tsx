import {Popover} from '@mui/material';
import {MOON_900, TEAL_300} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import {
  DraggableGrow,
  DraggableHandle,
} from '@wandb/weave/components/DraggablePopups';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {Icon, IconName} from '@wandb/weave/components/Icon';
import * as Switch from '@wandb/weave/components/Switch';
import {IconOnlyPill} from '@wandb/weave/components/Tag/Pill';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import {useLocalStorage} from '@wandb/weave/util/useLocalStorage';
import classNames from 'classnames';
import React, {useEffect, useMemo, useRef, useState} from 'react';
import {AutoSizer, List} from 'react-virtualized';

import {
  getCostFromCostData,
  getTokensFromUsage,
  TraceStat,
} from '../../../pages/CallPage/cost';
import {CallStatusType, StatusChip} from '../../../pages/common/StatusChip';
import {TraceCallSchema} from '../../../pages/wfReactInterface/traceServerClientTypes';
import {traceCallStatusCode} from '../../../pages/wfReactInterface/tsDataModelHooks';
import TraceScrubber, {ScrubberOption} from '../TraceScrubber';
import {
  AGENT_OP_NAMES,
  COMPLETION_OP_NAMES,
  IMAGE_OP_NAMES,
  TOOL_OP_NAMES,
} from './operationNames';
import {TraceTreeFlat, TraceViewProps} from './types';
import {formatDuration, getCallDisplayName} from './utils';

interface FlattenedNode {
  id: string;
  call: TraceCallSchema;
  level: number;
  isExpanded: boolean;
  isVisible: boolean;
  childrenIds: string[];
  hasDescendantErrors: boolean;
}

interface TreeNodeProps {
  node: FlattenedNode;
  style: React.CSSProperties;
  focusedCallId?: string;
  setFocusedCallId: (id: string) => void;
  rootCallId?: string;
  setRootCallId: (id: string) => void;
  onToggleExpand: (id: string) => void;
  deemphasizeCallIds?: string[];
  searchQuery?: string;
  visibleColumns: {
    tokens: boolean;
    cost: boolean;
    duration: boolean;
  };
}

const TreeNode: React.FC<TreeNodeProps> = ({
  node,
  style,
  focusedCallId,
  setFocusedCallId,
  setRootCallId,
  onToggleExpand,
  deemphasizeCallIds,
  searchQuery,
  visibleColumns,
}) => {
  const {id, call, level, isExpanded, childrenIds, hasDescendantErrors} = node;
  const duration = call.ended_at
    ? Date.parse(call.ended_at) - Date.parse(call.started_at)
    : null;

  const {cost, costToolTipContent} = getCostFromCostData(
    call.summary?.weave?.costs
  );
  const {tokens, tokenToolTipContent} = getTokensFromUsage(call.summary?.usage);

  const displayName = getCallDisplayName(call);
  const renderHighlightedText = () => {
    if (!searchQuery) {
      return displayName;
    }
    const searchLower = searchQuery.toLowerCase();
    const textLower = displayName.toLowerCase();

    // Note: could highlight multiple matches for better UX
    const index = textLower.indexOf(searchLower);

    if (index === -1) {
      return displayName;
    }

    return (
      <>
        {displayName.slice(0, index)}
        <span
          className={classNames(
            'font-semibold',
            'text-teal-600',
            'dark:text-teal-500'
          )}>
          {displayName.slice(index, index + searchQuery.length)}
        </span>
        {displayName.slice(index + searchQuery.length)}
      </>
    );
  };

  const chevronIcon: IconName = isExpanded ? 'chevron-down' : 'chevron-next';
  const isDeemphasized = deemphasizeCallIds?.includes(id);
  const hasChildren = childrenIds.length > 0;
  let statusCode: CallStatusType = traceCallStatusCode(call);
  if (hasDescendantErrors && statusCode === 'SUCCESS') {
    statusCode = 'DESCENDANT_ERROR';
  }
  const indentMultiplier = 14;

  return (
    <div style={style}>
      <div
        style={{
          opacity: isDeemphasized ? 0.7 : 1,
          backgroundColor: id === focusedCallId ? `${TEAL_300}52` : undefined,
          color: id === focusedCallId ? MOON_900 : undefined,
        }}
        onClick={() => setFocusedCallId(id)}
        onDoubleClick={() => setRootCallId(id)}
        className="h-[32px] w-full cursor-pointer select-none justify-start rounded-none px-8 text-left text-sm font-semibold tracking-normal text-moon-600 hover:bg-oblivion/[0.07] hover:text-moon-800 [&_svg]:h-18 [&_svg]:w-18">
        <div className="relative flex w-full items-center justify-between gap-8">
          <div className="flex min-w-0 flex-1 items-center">
            <div
              style={{marginLeft: level * indentMultiplier}}
              className={`h-[32px]`}
            />
            {/* Render vertical lines for each level of hierarchy */}
            {Array.from({length: level}).map((_, idx) => (
              <div
                key={`line-${idx}`}
                style={{left: idx * indentMultiplier, marginLeft: 8}}
                className="absolute top-0 h-full w-px border-l border-moon-200"
              />
            ))}
            {hasChildren ? (
              <Icon
                name={chevronIcon}
                size="small"
                onClick={(e: React.MouseEvent) => {
                  e.stopPropagation();
                  onToggleExpand(id);
                }}
                className="p-0.5 shrink-0 cursor-pointer rounded hover:bg-moon-300"
              />
            ) : (
              <div className="w-[18px]" />
            )}
            <div className="truncate pl-4 font-medium">
              <Tooltip
                trigger={
                  <div className="truncate">{renderHighlightedText()}</div>
                }
                content={<span>{displayName}</span>}
              />
            </div>
          </div>

          <div className="ml-8 flex shrink-0 items-center gap-4 text-xs text-moon-400">
            <div className="flex items-center gap-4 text-right">
              {/* Overflow tooltip for non-visible metrics */}
              {((tokens !== undefined && !visibleColumns.tokens) ||
                (cost !== undefined && !visibleColumns.cost) ||
                (duration !== null && !visibleColumns.duration)) && (
                <Tooltip
                  content={
                    <div className="flex flex-col gap-[8px]">
                      {tokens !== undefined && !visibleColumns.tokens && (
                        <div className="flex flex-col">
                          <p className="font-semibold">Token usage</p>
                          <p>{tokens}</p>
                        </div>
                      )}
                      {cost !== undefined && !visibleColumns.cost && (
                        <div className="flex flex-col">
                          <p className="font-semibold">Estimated cost</p>
                          <p>{cost}</p>
                        </div>
                      )}
                      {duration !== null && !visibleColumns.duration && (
                        <div className="flex flex-col">
                          <p className="font-semibold">Duration</p>
                          <p>{formatDuration(duration)}</p>
                        </div>
                      )}
                    </div>
                  }
                  trigger={
                    <div className="cursor-pointer">
                      <Icon
                        name="overflow-horizontal"
                        size="small"
                        className="text-moon-400"
                      />
                    </div>
                  }
                />
              )}

              {/* Visible metrics */}
              <div className="flex items-center gap-4">
                {visibleColumns.tokens &&
                  (tokens !== undefined ? (
                    <TraceStat
                      label={tokens}
                      tooltip={
                        <div className="text-white-800">
                          <span style={{fontWeight: 600}}>
                            Estimated tokens
                          </span>
                          {tokenToolTipContent}
                        </div>
                      }
                      className="min-w-[36px] justify-end px-0 text-xs text-moon-400"
                    />
                  ) : (
                    <span className="min-w-[36px] px-0 text-xs text-transparent">
                      -
                    </span>
                  ))}
                {visibleColumns.cost &&
                  (cost !== undefined ? (
                    <TraceStat
                      label={cost}
                      tooltip={
                        <div className="text-white-800">
                          {costToolTipContent}
                        </div>
                      }
                      className="ml-[4px] min-w-[46px] justify-end px-0 text-xs text-moon-400"
                    />
                  ) : (
                    <span className="ml-[4px] min-w-[46px] px-0 text-xs text-transparent">
                      -
                    </span>
                  ))}
                {visibleColumns.duration &&
                  (duration !== null ? (
                    <div className="flex items-center gap-1">
                      <span className="min-w-[36px] px-0 text-moon-400">
                        {formatDuration(duration)}
                      </span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1">
                      <span className="min-w-[36px] px-0 text-transparent">
                        -
                      </span>
                    </div>
                  ))}
              </div>
            </div>
            {statusCode === 'ERROR' || statusCode === 'UNSET' ? (
              <StatusChip value={statusCode} iconOnly />
            ) : statusCode === 'DESCENDANT_ERROR' && !isExpanded ? (
              <Tooltip
                content={
                  <span>
                    This call succeeded, but one or more descendants failed.
                  </span>
                }
                trigger={
                  <div className="flex h-[22px] w-[22px] items-center justify-center">
                    <div className="h-[5px] w-[5px] rounded-full bg-red-550" />
                  </div>
                }
              />
            ) : COMPLETION_OP_NAMES.some(opName =>
                node.call.op_name?.toLowerCase().includes(opName)
              ) ? (
              <IconOnlyPill icon="forum-chat-bubble" color="purple" />
            ) : TOOL_OP_NAMES.some(opName =>
                node.call.op_name?.toLowerCase().includes(opName)
              ) ? (
              <IconOnlyPill icon="code-alt" color="purple" />
            ) : IMAGE_OP_NAMES.some(opName =>
                node.call.op_name?.toLowerCase().includes(opName)
              ) ? (
              <IconOnlyPill icon="photo" color="purple" />
            ) : AGENT_OP_NAMES.some(opName =>
                node.call.op_name?.toLowerCase().includes(opName)
              ) ? (
              <IconOnlyPill icon="robot-service-member" color="blue" />
            ) : (
              // Else show spacer placeholder
              <div className="w-[22px]" />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

interface TreeViewHeaderProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  strictSearch: boolean;
  onToggleStrictSearch: () => void;
  visibleColumns: {
    tokens: boolean;
    cost: boolean;
    duration: boolean;
  };
  onToggleColumnVisibility: (
    column: keyof TreeViewHeaderProps['visibleColumns']
  ) => void;
}

const TreeViewHeader: React.FC<TreeViewHeaderProps> = ({
  searchQuery,
  onSearchChange,
  strictSearch,
  onToggleStrictSearch,
  visibleColumns,
  onToggleColumnVisibility,
}) => {
  const buttonRef = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : buttonRef.current);
  };
  const handleClose = () => {
    setAnchorEl(null);
  };
  const open = Boolean(anchorEl);
  const columnLabels: Record<keyof typeof visibleColumns, string> = {
    tokens: 'Token usage',
    cost: 'Cost',
    duration: 'Duration',
  };

  return (
    <div className="flex items-center p-8 text-sm">
      <TextField
        value={searchQuery}
        onChange={onSearchChange}
        placeholder="Filter by op name..."
        icon="filter-alt"
        extraActions={
          searchQuery !== '' && (
            <>
              <Button
                variant="ghost"
                size="small"
                onClick={onToggleStrictSearch}
                tooltip={
                  strictSearch
                    ? '(Strict) Only show matching nodes'
                    : '(Loose) Show children of matching nodes'
                }
                className={strictSearch ? 'mr-2' : 'mr-2 text-moon-500'}
                active={strictSearch}>
                Strict
              </Button>
              <Button
                variant="ghost"
                size="small"
                icon="close"
                onClick={() => onSearchChange('')}
                className="mr-6"
              />
            </>
          )
        }
      />
      <div ref={buttonRef} className="ml-4">
        <Button
          variant="ghost"
          icon="column"
          tooltip="Manage fields"
          onClick={handleClick}
        />
      </div>
      <Popover
        open={open}
        anchorEl={anchorEl}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
        onClose={handleClose}
        slotProps={{
          paper: {
            sx: {
              overflow: 'visible',
            },
          },
        }}
        TransitionComponent={DraggableGrow}>
        <Tailwind>
          <div className="min-w-[150px] p-12">
            <DraggableHandle>
              <div className="flex items-center pb-8">
                <div className="flex-auto font-semibold">Manage fields</div>
              </div>
            </DraggableHandle>
            <div className="max-h-[300px] overflow-auto">
              {Object.entries(visibleColumns).map(([column, isVisible]) => {
                const idSwitch = `toggle-vis_${column}`;
                const columnKey = column as keyof typeof visibleColumns;
                return (
                  <div key={column}>
                    <div className="flex items-center py-2">
                      <Switch.Root
                        id={idSwitch}
                        size="small"
                        checked={isVisible}
                        onCheckedChange={() =>
                          onToggleColumnVisibility(columnKey)
                        }>
                        <Switch.Thumb size="small" checked={isVisible} />
                      </Switch.Root>
                      <label htmlFor={idSwitch} className="ml-6 cursor-pointer">
                        {columnLabels[columnKey]}
                      </label>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </Tailwind>
      </Popover>
    </div>
  );
};

export const FilterableTreeView: React.FC<TraceViewProps> = props => {
  const [searchQuery, setSearchQuery] = useState('');
  const [strictSearch, setStrictSearch] = useState(false);
  const [visibleColumns, setVisibleColumns] = useLocalStorage(
    'traceViewVisibleColumns',
    {
      tokens: false,
      cost: false,
      duration: false,
    }
  );

  const handleToggleColumnVisibility = (
    column: keyof typeof visibleColumns
  ) => {
    setVisibleColumns({
      ...visibleColumns,
      [column]: !visibleColumns[column],
    });
  };

  const [matchedCallIds, filteredCallIds, deemphasizeCallIds] = useMemo(() => {
    // First find direct matches
    const directMatches = Object.entries(props.traceTreeFlat)
      .filter(([_, node]) => {
        return (
          searchQuery === '' ||
          getCallDisplayName(node.call)
            .toLowerCase()
            .includes(searchQuery.toLowerCase())
        );
      })
      .map(([id]) => id);

    const foundCallIds = new Set<string>(directMatches);
    const filteredCallIdsSet = new Set(directMatches);

    // Process queue for both upward (parents) and downward (children)
    const itemsToProcess = [...directMatches];

    while (itemsToProcess.length > 0) {
      const id = itemsToProcess.shift();
      if (id) {
        const node = props.traceTreeFlat[id];

        // Add parents
        if (node.parentId) {
          filteredCallIdsSet.add(node.parentId);
          if (!foundCallIds.has(node.parentId)) {
            itemsToProcess.push(node.parentId);
          }
        }

        // Only add children of direct matches if not in strict search mode
        // Don't add children of parent nodes that were added just to show the path
        if (foundCallIds.has(id) && !strictSearch) {
          // Add all children recursively
          const addChildren = (nodeId: string) => {
            const currentNode = props.traceTreeFlat[nodeId];
            if (currentNode && currentNode.childrenIds) {
              for (const childId of currentNode.childrenIds) {
                if (!filteredCallIdsSet.has(childId)) {
                  filteredCallIdsSet.add(childId);
                  addChildren(childId);
                }
              }
            }
          };

          addChildren(id);
        }
      }
    }

    return [
      directMatches,
      Array.from(filteredCallIdsSet),
      Array.from(
        new Set([...filteredCallIdsSet].filter(x => !foundCallIds.has(x)))
      ),
    ];
  }, [props.traceTreeFlat, searchQuery, strictSearch]);

  const scrubbers: ScrubberOption[] = useMemo(() => {
    if (searchQuery === '') {
      return ['timeline', 'peer', 'sibling', 'stack'];
    }
    return ['timeline'];
  }, [searchQuery]);

  // Derived data
  const traceTreeFlat = useMemo(() => {
    if (searchQuery === '') {
      return props.traceTreeFlat;
    }
    const matched = new Set<string>(matchedCallIds);
    return Object.fromEntries(
      Object.entries(props.traceTreeFlat).filter(([_, node]) => {
        return matched.has(node.id);
      })
    );
  }, [matchedCallIds, props.traceTreeFlat, searchQuery]);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <TreeViewHeader
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        strictSearch={strictSearch}
        onToggleStrictSearch={() => setStrictSearch(!strictSearch)}
        visibleColumns={visibleColumns}
        onToggleColumnVisibility={handleToggleColumnVisibility}
      />
      <div className="flex-1 overflow-hidden">
        <TreeView
          {...props}
          filterCallIds={filteredCallIds}
          deemphasizeCallIds={deemphasizeCallIds}
          searchQuery={searchQuery}
          visibleColumns={visibleColumns}
        />
      </div>
      <TraceScrubber
        {...props}
        allowedScrubbers={scrubbers}
        traceTreeFlat={traceTreeFlat}
      />
    </div>
  );
};

export const TreeView: React.FC<
  TraceViewProps & {
    filterCallIds?: string[];
    deemphasizeCallIds?: string[];
    searchQuery?: string;
    visibleColumns: {
      tokens: boolean;
      cost: boolean;
      duration: boolean;
    };
  }
> = ({
  traceTreeFlat,
  focusedCallId,
  setFocusedCallId,
  filterCallIds,
  deemphasizeCallIds,
  setRootCallId,
  searchQuery,
  visibleColumns,
}) => {
  // Initialize expandedNodes with all node IDs
  const [collapsedNodes, setCollapsedNodes] = useState<Set<string>>(
    () => new Set([])
  );

  const filterSet = useMemo(
    () => (filterCallIds ? new Set(filterCallIds) : undefined),
    [filterCallIds]
  );

  const listRef = useRef<List>(null);

  const rootNodes = useMemo(() => {
    if (!filterCallIds || filterCallIds.length === 0) {
      return Object.values(traceTreeFlat).filter(
        node => !node.parentId || !traceTreeFlat[node.parentId]
      );
    }

    const filterIdSet = new Set(filterCallIds);
    return Object.values(traceTreeFlat).filter(node => {
      if (!filterIdSet.has(node.id)) {
        return false;
      }
      return (
        !node.parentId ||
        !traceTreeFlat[node.parentId] ||
        !filterIdSet.has(node.parentId)
      );
    });
  }, [traceTreeFlat, filterCallIds]);

  const flattenedNodes = useMemo(() => {
    const result: FlattenedNode[] = [];
    const processNode = (node: TraceTreeFlat[string], level: number) => {
      const isExpanded = !collapsedNodes.has(node.id);
      const filteredChildren = node.childrenIds.filter(childId => {
        return !filterSet || filterSet.has(childId);
      });
      result.push({
        id: node.id,
        call: node.call,
        level,
        isExpanded,
        isVisible: true,
        childrenIds: filteredChildren,
        hasDescendantErrors: node.descendantHasErrors,
      });

      if (isExpanded) {
        filteredChildren.forEach((childId: string) => {
          const child = traceTreeFlat[childId];
          if (child && (!filterSet || filterSet.has(childId))) {
            processNode(child, level + 1);
          }
        });
      }
    };

    rootNodes.forEach(node => processNode(node, 0));
    return result;
  }, [rootNodes, traceTreeFlat, collapsedNodes, filterSet]);

  const handleToggleExpand = (id: string) => {
    const newExpandedNodes = new Set(collapsedNodes);
    if (newExpandedNodes.has(id)) {
      // When expanding, only remove current node from collapsed nodes
      newExpandedNodes.delete(id);
    } else {
      // When collapsing, we add this node and all its descendants to collapsed nodes
      const addDescendants = (nodeId: string) => {
        newExpandedNodes.add(nodeId);
        const node = traceTreeFlat[nodeId];
        if (node) {
          node.childrenIds.forEach(childId => {
            addDescendants(childId);
          });
        }
      };
      addDescendants(id);
    }
    setCollapsedNodes(newExpandedNodes);
  };

  const rowRenderer = ({index, style}: any) => {
    const node = flattenedNodes[index];
    return (
      <TreeNode
        key={node.id}
        node={node}
        style={style}
        focusedCallId={focusedCallId}
        setFocusedCallId={setFocusedCallId}
        setRootCallId={setRootCallId}
        onToggleExpand={handleToggleExpand}
        deemphasizeCallIds={deemphasizeCallIds}
        searchQuery={searchQuery}
        visibleColumns={visibleColumns}
      />
    );
  };

  // Scroll when selectedCallId changes
  useEffect(() => {
    const scrollToSelectedRow = () => {
      if (!focusedCallId || !listRef.current) {
        return;
      }

      const selectedIndex = flattenedNodes.findIndex(
        (node: FlattenedNode) => node.id === focusedCallId
      );
      if (selectedIndex === -1) {
        return;
      }

      listRef.current.scrollToRow(selectedIndex);
    };

    const timer = setTimeout(scrollToSelectedRow, 0);
    return () => clearTimeout(timer);
  }, [focusedCallId, flattenedNodes]);

  return (
    <div className="h-full overflow-hidden">
      <AutoSizer>
        {({width, height}) => (
          <List
            ref={listRef}
            width={width}
            height={height}
            rowCount={flattenedNodes.length}
            rowHeight={32}
            rowRenderer={rowRenderer}
            overscanRowCount={10}
            scrollToAlignment="auto"
          />
        )}
      </AutoSizer>
    </div>
  );
};
