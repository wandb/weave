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
import {isMessage} from '../ChatView/hooks';
import {useWFHooks} from '../wfReactInterface/context';

// Helper function to get the last message content
const getLastMessageContent = (call: CallSchema): { userMessage: string | null; aiResponse: string | null } => {
  console.log('Getting last message from call:', {
    hasTraceCall: !!call.traceCall,
    hasInputs: !!call.traceCall?.inputs,
    inputsKeys: call.traceCall?.inputs ? Object.keys(call.traceCall.inputs) : [],
    rawSpanAttributes: call.rawSpan?.attributes,
    output: call.traceCall?.output
  });

  // Try different possible locations for messages
  const messages = 
    call.traceCall?.inputs?.messages || // Direct messages array
    call.traceCall?.inputs?.input?.messages || // Nested in input object
    call.rawSpan?.attributes?.messages || // In span attributes
    (call.traceCall?.inputs?.input && JSON.parse(call.traceCall.inputs.input).messages); // JSON string in input

  if (!messages || !Array.isArray(messages)) {
    return { userMessage: null, aiResponse: null };
  }

  console.log('Found messages array:', messages);

  let userMessage: string | null = null;
  let aiResponse: string | null = null;

  // Find the last user message
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i];
    if (isMessage(message) && message.role === 'user' && typeof message.content === 'string' && !userMessage) {
      userMessage = message.content;
      break;
    }
  }

  // Try to get AI response from different possible locations
  aiResponse = (() => {
    // Try to get from output choices first
    const output = call.traceCall?.output as { choices?: Array<{ message?: { content?: string }, text?: string }> } | undefined;
    if (output?.choices && Array.isArray(output.choices) && output.choices.length > 0) {
      const choice = output.choices[0];
      if (choice?.message?.content) {
        return choice.message.content;
      }
      if (typeof choice?.text === 'string') {
        return choice.text;
      }
    }

    // If no choices, try to get from messages array
    for (let i = messages.length - 1; i >= 0; i--) {
      const message = messages[i];
      if (isMessage(message) && message.role === 'assistant' && typeof message.content === 'string') {
        return message.content;
      }
    }

    return null;
  })();

  return { userMessage, aiResponse };
};

// Helper function to check if a call is an AI call
const isAICall = (call: CallSchema): boolean => {
  const callName = call.spanName || call.rawSpan?.name;
  console.log('Checking call:', {
    spanName: call.spanName,
    rawSpanName: call.rawSpan?.name,
    isAI: aiCallTypes.includes(callName)
  });
  return aiCallTypes.includes(callName);
};

// Define AI call types
const aiCallTypes = [
  'openai.chat.completions.create',
  'anthropic.Messages.create',
  'anthropic.AsyncMessages.create'
];

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

const QAContainer = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  padding: 0px 4px;
`;

const MessageContainer = styled.div`
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 85%;
  font-size: 14px;
  border-radius: 8px;
`;

const QuestionContainer = styled(MessageContainer)`
  color: #fff;
  background-color: #155B69;
  padding: 4px 8px;
  margin-left: auto;
`;

const AnswerContainer = styled(MessageContainer)`
  margin-right: auto;
`;

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
  const {useCall} = useWFHooks();

  // Get the root call ID outside of useMemo
  const rootCallId = useMemo(() => {
    const callRows = rows.filter(row => 'call' in row) as CallRow[];
    const sortedCalls = _.sortBy(callRows, 
      row => row.call.rawSpan.start_time_ms
    );
    return sortedCalls.length > 0 ? sortedCalls[0].id : null;
  }, [rows]);

  // Get all AI call IDs
  const aiCallIds = useMemo(() => {
    return rows
      .filter(row => 'call' in row && isAICall((row as CallRow).call))
      .map(row => (row as CallRow).call.callId);
  }, [rows]);

  // Fetch complete data for all AI calls
  const aiCallsData = aiCallIds.map(callId =>
    useCall({
      entity: call.entity,
      project: call.project,
      callId,
    })
  );

  // Create a map of complete call data
  const completeCallDataMap = useMemo(() => {
    const map = new Map<string, CallSchema>();
    aiCallsData.forEach((callData, index) => {
      if (!callData.loading && callData.result) {
        map.set(aiCallIds[index], callData.result);
      }
    });
    return map;
  }, [aiCallsData, aiCallIds]);

  // Group and sort rows
  const groupedRows = useMemo(() => {
    const callRows = rows.filter(row => 'call' in row) as CallRow[];
    
    // First, sort all calls by start time
    const sortedCalls = _.sortBy(callRows, 
      row => row.call.rawSpan.start_time_ms
    );

    // Initialize arrays
    let currentGroup: CallRow[] = [];
    const finalRows: Row[] = [];

    // Always add the first call at the top if it exists
    if (sortedCalls.length > 0) {
      const rootCall = sortedCalls[0];
      finalRows.push({
        ...rootCall,
        hierarchy: [rootCall.id]
      });

      // Process remaining calls
      sortedCalls.slice(1).forEach(row => {
        const isAiCall = aiCallTypes.includes(row.call.spanName) || 
                        aiCallTypes.includes(row.call.rawSpan.name);

        if (isAiCall) {
          // If we have accumulated non-AI calls, create a group
          if (currentGroup.length > 0) {
            const groupId = `non-ai-group-${finalRows.length}`;
            
            // Add group header at top level
            finalRows.push({
              id: groupId,
              groupName: 'Tools and functions',
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
              padding: '0 24px',
              height: '100%'
            }}>
              <div style={{ 
                display: 'flex',
                alignItems: 'center',
                color: MOON_500
              }}>
                <Icon
                  name={expandedGroups.has(params.row.id) ? 'chevron-down' : 'chevron-next'}
                />
              </div>
              <span style={{ color: MOON_500 }}>{params.row.groupName} ({params.row.count})</span>
            </div>
          );
        }

        // Check if this is the first call we placed at the top
        const isFirstCall = params.row.id === rootCallId;
        
        // Check if this is a non-AI call (child of a group)
        const isNonAiCall = params.row.hierarchy.length > 1;

        // Get the display name for AI calls
        const displayName = (() => {
          if ('call' in params.row) {
            const call = params.row.call;
            if (isAICall(call)) {
              // Use the complete call data if available
              const completeCallData = completeCallDataMap.get(call.callId);
              if (completeCallData) {
                const { userMessage, aiResponse } = getLastMessageContent(completeCallData);
                if (userMessage) {
                  const truncatedUser = userMessage.length > 50 ? userMessage.substring(0, 47) + '...' : userMessage;
                  const truncatedAI = aiResponse && aiResponse.length > 50 ? aiResponse.substring(0, 47) + '...' : aiResponse;
                  
                  return (
                    <QAContainer>
                      <QuestionContainer>{truncatedUser}</QuestionContainer>
                      {aiResponse && <AnswerContainer>{truncatedAI}</AnswerContainer>}
                    </QAContainer>
                  );
                }
              }
            }
          }
          return undefined;
        })();
        
        return (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            width: '100%',
            paddingTop: isNonAiCall ? '16px' : '0',
            paddingBottom: isNonAiCall ? '16px' : '0',
            paddingLeft: isNonAiCall ? '16px' : '8px',
            marginLeft: isNonAiCall ? '16px' : '0',
            position: 'relative',
            fontWeight: isFirstCall ? 600 : 'normal'
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
              style={{ paddingTop: 0 }}
              displayName={displayName}
            />
          </div>
        );
      },
    }),
    [costLoading, expandedGroups, rootCallId, aiCallTypes, completeCallDataMap]
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
          padding: 0,
        },
        '& div div div div >.MuiDataGrid-cell:focus': {
          outline: 'none',
        }
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
          getRowHeight={params => {
            if ('isGroupHeader' in params.model) {
              return 40; // Group header height
            }
            if ('call' in params.model) {
              return isAICall(params.model.call) ? 112 : 64; // AI calls get 112px, other calls get 64px
            }
            return 52; // Default height for any other row types
          }}
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