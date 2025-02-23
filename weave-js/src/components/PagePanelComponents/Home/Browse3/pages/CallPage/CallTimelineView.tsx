import {
  DataGridPro,
  DataGridProProps,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {FC, useCallback, useEffect, useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import {ErrorBoundary} from '../../../../../ErrorBoundary';
import {useWeaveflowCurrentRouteContext} from '../../context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {CustomGridTreeDataGroupingCell} from './CustomGridTreeDataGroupingCell';
import {CallStatusType} from '../common/StatusChip';
import {Icon} from '../../../../../Icon';
import {MOON_500} from '../../../../../../common/css/color.styles';

// Import the types from CallTraceView
type GroupHeaderRow = {
  id: string;
  groupName: string;
  count: number;
  hierarchy: string[];
  isGroupHeader: true;
};

type CallRow = {
  id: string;
  call: CallSchema;
  status: CallStatusType;
  hierarchy: string[];
  path: string;
  isTraceRootCall: boolean;
  isParentRow?: boolean;
};

type SiblingCountRow = {
  id: 'HIDDEN_SIBLING_COUNT';
  count: number;
  hierarchy: string[];
};

type HiddenChildrenCountRow = {
  id: string; // <id>_HIDDEN_CHILDREN_COUNT
  count: number;
  hierarchy: string[];
  parentId: string;
};

type Row = CallRow | SiblingCountRow | HiddenChildrenCountRow | GroupHeaderRow;

const CallTimeline = styled.div`
  overflow: auto;
  height: 100%;
`;
CallTimeline.displayName = 'S.CallTimeline';

export const CallTimelineView: FC<{
  call: CallSchema;
  selectedCall: CallSchema;
  rows: Row[];
  costLoading: boolean;
}> = ({call, selectedCall, rows, costLoading}) => {
  const apiRef = useGridApiRef();
  const history = useHistory();
  const currentRouter = useWeaveflowCurrentRouteContext();
  const [suppressScroll, setSuppressScroll] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState(new Set<string>());

  // Define AI call types
  const aiCallTypes = [
    'openai.chat.completions.create',
    'anthropic.Messages.create',
    'anthropic.AsyncMessages.create'
  ];

  // Group and sort rows
  const groupedRows = useMemo(() => {
    const callRows = rows.filter(row => 'call' in row) as CallRow[];
    
    // First, sort all calls by start time
    const sortedCalls = _.sortBy(callRows, 
      row => row.call.rawSpan.start_time_ms
    );

    // Separate into AI and non-AI calls while preserving order
    let currentGroup: CallRow[] = [];
    const finalRows: Row[] = [];

    sortedCalls.forEach((row, index) => {
      const isAiCall = aiCallTypes.includes(row.call.spanName) || 
                      aiCallTypes.includes(row.call.rawSpan.name);

      if (isAiCall) {
        // If we have accumulated non-AI calls, create a group
        if (currentGroup.length > 0) {
          const groupId = `non-ai-group-${finalRows.length}`;
          
          // Add group header at top level
          finalRows.push({
            id: groupId,
            groupName: 'Other Calls',
            count: currentGroup.length,
            hierarchy: [groupId],
            isGroupHeader: true
          });

          // Add non-AI calls under the group
          currentGroup.forEach(call => {
            finalRows.push({
              ...call,
              hierarchy: [groupId, call.id]
            });
          });
          
          currentGroup = [];
        }

        // Add AI call at top level
        finalRows.push({
          ...row,
          hierarchy: [row.id]
        });
      } else {
        currentGroup.push(row);
      }
    });

    // Handle any remaining non-AI calls
    if (currentGroup.length > 0) {
      const groupId = `non-ai-group-${finalRows.length}`;
      
      finalRows.push({
        id: groupId,
        groupName: 'Other Calls',
        count: currentGroup.length,
        hierarchy: [groupId],
        isGroupHeader: true
      });

      currentGroup.forEach(call => {
        finalRows.push({
          ...call,
          hierarchy: [groupId, call.id]
        });
      });
    }

    return finalRows;
  }, [rows, aiCallTypes]);

  // Update grouping column definition to handle group headers
  const groupingColDef: DataGridProProps['groupingColDef'] = useMemo(
    () => ({
      headerName: 'Timeline',
      headerAlign: 'center',
      flex: 1,
      display: 'flex',
      renderCell: params => {
        if ('isGroupHeader' in params.row) {
          return (
            <div style={{ 
              display: 'flex', 
              alignItems: 'center',
              cursor: 'pointer',
              padding: '0 8px',
              height: '100%'
            }}>
              <div style={{ 
                marginRight: '8px',
                display: 'flex',
                alignItems: 'center',
                color: MOON_500
              }}>
                <Icon
                  name={expandedGroups.has(params.row.id) ? 'chevron-down' : 'chevron-next'}
                />
              </div>
              <span>{params.row.groupName} ({params.row.count})</span>
            </div>
          );
        }

        // Check if this is a non-AI call (child of a group)
        const isNonAiCall = params.row.hierarchy.length > 1;
        
        return (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            width: '100%',
            paddingLeft: isNonAiCall ? '32px' : '8px',
            position: 'relative'
          }}>
            {isNonAiCall && (
              <div style={{
                position: 'absolute',
                left: '16px',
                top: 0,
                bottom: 0,
                width: '2px',
                backgroundColor: '#e0e0e0'
              }} />
            )}
            <CustomGridTreeDataGroupingCell
              {...params}
              costLoading={costLoading}
              showTreeControls={false}
            />
          </div>
        );
      },
    }),
    [costLoading, expandedGroups]
  );

  // Handle row clicks including group headers
  const onRowClick: DataGridProProps['onRowClick'] = useCallback(
    params => {
      if ('isGroupHeader' in params.row) {
        setExpandedGroups(prev => {
          const newSet = new Set(prev);
          if (newSet.has(params.row.id)) {
            newSet.delete(params.row.id);
          } else {
            newSet.add(params.row.id);
          }
          return newSet;
        });
        return;
      }

      if (!params.row.call) {
        return;
      }
      const rowCall = params.row.call as CallSchema;
      setSuppressScroll(true);
      history.replace(
        currentRouter.callUIUrl(
          call.entity,
          call.project,
          call.traceId,
          call.callId,
          params.row.path,
          true
        )
      );
    },
    [call.callId, call.entity, call.project, call.traceId, currentRouter, history]
  );

  // Style the selected call
  const callClass = `.callId-${selectedCall.callId}`;
  const getRowClassName: DataGridProProps['getRowClassName'] = useCallback(
    params => {
      if (!params.row.call) {
        return '';
      }
      const rowCall = params.row.call as CallSchema;
      return `callId-${rowCall.callId}`;
    },
    []
  );

  // Grid styling
  const sx: DataGridProProps['sx'] = useMemo(
    () => ({
      border: 0,
      fontFamily: 'Source Sans Pro',
      '&>.MuiDataGrid-main': {
        '& div div div div >.MuiDataGrid-cell': {
          borderTop: 'none',
        },
        '& div div div div >.MuiDataGrid-cell:focus': {
          outline: 'none',
        },
      },
      '& .MuiDataGrid-topContainer': {
        display: 'none',
      },
      '& .MuiDataGrid-columnHeaders': {
        borderBottom: 'none',
      },
      '& .MuiDataGrid-filler': {
        display: 'none',
      },
      [callClass]: {
        backgroundColor: '#a9edf252',
      },
    }),
    [callClass]
  );

  // Scroll selected call into view
  const callId = selectedCall.callId;
  useEffect(() => {
    const t = setTimeout(() => {
      if (suppressScroll) {
        setSuppressScroll(false);
        return;
      }
      const rowElement = apiRef.current.getRowElement(callId);
      if (rowElement) {
        rowElement.scrollIntoView();
      } else {
        const rowIndex = apiRef.current.getRowIndexRelativeToVisibleRows(callId);
        apiRef.current.scrollToIndexes({rowIndex});
      }
      setSuppressScroll(false);
    }, 0);
    return () => clearTimeout(t);
  }, [apiRef, callId, suppressScroll]);

  // Animation buffer for initial load
  const [animationBuffer, setAnimationBuffer] = useState(true);
  useEffect(() => {
    setTimeout(() => {
      setAnimationBuffer(false);
    }, 0);
  }, []);

  // Update isGroupExpandedByDefault
  const isGroupExpandedByDefault: DataGridProProps['isGroupExpandedByDefault'] = useCallback(
    node => expandedGroups.has(node.groupingKey?.toString() ?? ''),
    [expandedGroups]
  );

  // Add getTreeDataPath prop
  const getTreeDataPath: DataGridProProps['getTreeDataPath'] = useCallback(
    row => row.hierarchy,
    []
  );

  return (
    <CallTimeline>
      <ErrorBoundary>
        <DataGridPro
          apiRef={apiRef}
          getRowHeight={params => ('isGroupHeader' in params.model ? 32 : 64)}
          columnHeaderHeight={0}
          treeData
          loading={animationBuffer}
          onRowClick={onRowClick}
          rows={animationBuffer ? [] : groupedRows}
          columns={[]}
          getTreeDataPath={getTreeDataPath}
          groupingColDef={groupingColDef}
          isGroupExpandedByDefault={isGroupExpandedByDefault}
          getRowClassName={getRowClassName}
          hideFooter
          rowSelection={false}
          sx={sx}
        />
      </ErrorBoundary>
    </CallTimeline>
  );
}; 