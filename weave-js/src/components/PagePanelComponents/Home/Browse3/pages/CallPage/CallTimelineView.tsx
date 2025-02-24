import {
  DataGridPro,
  DataGridProProps,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {FC, useCallback, useEffect, useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import {MOON_500} from '../../../../../../common/css/color.styles';
import {ErrorBoundary} from '../../../../../ErrorBoundary';
import {Icon} from '../../../../../Icon';
import {useWeaveflowCurrentRouteContext} from '../../context';
import {isMessage} from '../ChatView/hooks';
import {CallStatusType} from '../common/StatusChip';
import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {CustomGridTreeDataGroupingCell} from './CustomGridTreeDataGroupingCell';

// Helper function to get the last message content
const getLastMessageContent = (
  call: CallSchema
): {userMessage: string | null; aiResponse: string | null} => {
  console.log('Getting last message from call:', {
    hasTraceCall: !!call.traceCall,
    hasInputs: !!call.traceCall?.inputs,
    inputsKeys: call.traceCall?.inputs
      ? Object.keys(call.traceCall.inputs)
      : [],
    rawSpanAttributes: call.rawSpan?.attributes,
    output: call.traceCall?.output,
  });

  // Try different possible locations for messages
  const messages =
    call.traceCall?.inputs?.messages || // Direct messages array
    call.traceCall?.inputs?.input?.messages || // Nested in input object
    call.rawSpan?.attributes?.messages || // In span attributes
    (call.traceCall?.inputs?.input &&
      JSON.parse(call.traceCall.inputs.input).messages); // JSON string in input

  if (!messages || !Array.isArray(messages)) {
    return {userMessage: null, aiResponse: null};
  }

  console.log('Found messages array:', messages);

  // Get the last message regardless of role
  const lastMessage = messages[messages.length - 1];
  const userMessage =
    isMessage(lastMessage) && typeof lastMessage.content === 'string'
      ? lastMessage.content
      : null;

  // Try to get AI response from different possible locations
  const aiResponse = (() => {
    // Try to get from output choices first
    const output = call.traceCall?.output as
      | {choices?: Array<{message?: {content?: string}; text?: string}>}
      | undefined;
    if (
      output?.choices &&
      Array.isArray(output.choices) &&
      output.choices.length > 0
    ) {
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
      if (
        isMessage(message) &&
        message.role === 'assistant' &&
        typeof message.content === 'string'
      ) {
        return message.content;
      }
    }

    return null;
  })();

  return {userMessage, aiResponse};
};

// Helper function to check if a call is an AI call
const isAICall = (call: CallSchema): boolean => {
  const callName = call.spanName || call.rawSpan?.name;
  console.log('Checking call:', {
    spanName: call.spanName,
    rawSpanName: call.rawSpan?.name,
    isAI: aiCallTypes.includes(callName),
  });
  return aiCallTypes.includes(callName);
};

// Define AI call types
const aiCallTypes = [
  'openai.chat.completions.create',
  'anthropic.Messages.create',
  'anthropic.AsyncMessages.create',
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
  background-color: #155b69;
  padding: 4px 8px;
  margin-left: auto;
`;

const AnswerContainer = styled(MessageContainer)`
  margin-right: auto;
`;

// Create a wrapper component that handles remounting
const CallTimelineWrapper: FC<{
  call: CallSchema;
  selectedCall: CallSchema;
  rows: Row[];
  costLoading: boolean;
}> = props => {
  // Use the trace ID as the key to force remount when it changes
  return <CallTimelineView key={props.call.traceId} {...props} />;
};

// Custom hook to handle multiple calls
const useCallResults = (
  ids: string[],
  entity: string,
  project: string,
  useCall: any
) => {
  // Create separate hooks for each ID
  const results = ids.map(id => {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    return useCall({
      entity,
      project,
      callId: id,
    });
  });

  return useMemo(() => {
    const map = new Map<string, CallSchema>();
    results.forEach((result, index) => {
      if (!result?.loading && result?.result) {
        map.set(ids[index], result.result);
      }
    });
    return map;
  }, [results, ids]);
};

// Main component implementation
const CallTimelineView: FC<{
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

  // Ensure we have valid rows
  const safeRows = useMemo(() => rows || [], [rows]);

  // Get all AI call IDs
  const aiCallIds = useMemo(() => {
    if (!Array.isArray(safeRows)) {
      return [];
    }
    return safeRows
      .filter(
        row =>
          row &&
          'call' in row &&
          (row as CallRow).call &&
          isAICall((row as CallRow).call)
      )
      .map(row => (row as CallRow).call.callId)
      .filter(Boolean);
  }, [safeRows]);

  // Get call results using the custom hook
  const completeCallDataMap = useCallResults(
    aiCallIds,
    call.entity,
    call.project,
    useCall
  );

  // Process rows into groups
  const processedRows = useMemo(() => {
    if (!Array.isArray(safeRows)) {
      return [];
    }

    const validRows = safeRows.filter(
      row => row && 'call' in row && row.call?.rawSpan?.start_time_ms != null
    ) as CallRow[];

    const sortedCalls = _.sortBy(
      validRows,
      row => row.call.rawSpan.start_time_ms
    );
    if (sortedCalls.length === 0) {
      return [];
    }

    const finalRows: Row[] = [];
    let currentGroup: CallRow[] = [];
    const rootCall = sortedCalls[0];

    // Add root call
    if (rootCall && rootCall.id) {
      finalRows.push({
        ...rootCall,
        hierarchy: [rootCall.id],
      });

      // Process remaining calls
      for (const row of sortedCalls.slice(1)) {
        if (!row?.call?.spanName && !row?.call?.rawSpan?.name) {
          continue;
        }

        const isAiCall =
          (row.call.spanName && aiCallTypes.includes(row.call.spanName)) ||
          (row.call.rawSpan.name &&
            aiCallTypes.includes(row.call.rawSpan.name));

        if (isAiCall) {
          // Handle existing group if any
          if (currentGroup.length > 0) {
            const groupId = `non-ai-group-${finalRows.length}`;
            finalRows.push({
              id: groupId,
              groupName: 'Tools and functions',
              count: currentGroup.length,
              hierarchy: [groupId],
              isGroupHeader: true,
            });

            // Add group items
            currentGroup.forEach(groupItem => {
              if (groupItem?.id) {
                finalRows.push({
                  ...groupItem,
                  hierarchy: [groupId, groupItem.id],
                });
              }
            });
            currentGroup = [];
          }

          // Add AI call
          if (row.id) {
            finalRows.push({
              ...row,
              hierarchy: [row.id],
            });
          }
        } else {
          currentGroup.push(row);
        }
      }

      // Handle any remaining group items
      if (currentGroup.length > 0) {
        const groupId = `non-ai-group-${finalRows.length}`;
        finalRows.push({
          id: groupId,
          groupName: 'Other Calls',
          count: currentGroup.length,
          hierarchy: [groupId],
          isGroupHeader: true,
        });

        currentGroup.forEach(groupItem => {
          if (groupItem?.id) {
            finalRows.push({
              ...groupItem,
              hierarchy: [groupId, groupItem.id],
            });
          }
        });
      }
    }

    return finalRows;
  }, [safeRows]);

  // Get root call ID
  const rootCallId = useMemo(() => {
    return processedRows[0]?.id || null;
  }, [processedRows]);

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
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                cursor: 'pointer',
                padding: '0 20px',
                height: '100%',
              }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  color: MOON_500,
                }}>
                <Icon
                  name={
                    expandedGroups.has(params.row.id)
                      ? 'chevron-down'
                      : 'chevron-next'
                  }
                />
              </div>
              <span style={{marginLeft: '8px', color: MOON_500}}>
                {params.row.groupName} ({params.row.count})
              </span>
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
            const currentCall = params.row.call;
            if (isAICall(currentCall)) {
              // Use the complete call data if available
              const completeCallData = completeCallDataMap.get(
                currentCall.callId
              );
              if (completeCallData) {
                const {userMessage, aiResponse} =
                  getLastMessageContent(completeCallData);
                if (userMessage) {
                  const truncatedUser =
                    userMessage.length > 50
                      ? userMessage.substring(0, 47) + '...'
                      : userMessage;
                  const truncatedAI =
                    aiResponse && aiResponse.length > 50
                      ? aiResponse.substring(0, 47) + '...'
                      : aiResponse;

                  return (
                    <QAContainer>
                      <QuestionContainer>{truncatedUser}</QuestionContainer>
                      {aiResponse && (
                        <AnswerContainer>{truncatedAI}</AnswerContainer>
                      )}
                    </QAContainer>
                  );
                }
              }
            }
          }
          return undefined;
        })();

        return (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              width: '100%',
              paddingTop: isNonAiCall ? '16px' : '0',
              paddingBottom: isNonAiCall ? '16px' : '0',
              paddingLeft: isNonAiCall ? '21px' : '8px',
              marginLeft: isNonAiCall ? '13px' : '0',
              position: 'relative',
              fontWeight: isFirstCall ? 600 : 'normal',
            }}>
            {isNonAiCall && (
              <div
                style={{
                  position: 'absolute',
                  left: '16px',
                  top: 0,
                  bottom: 0,
                  width: '2px',
                  backgroundColor: '#e0e0e0',
                }}
              />
            )}
            <CustomGridTreeDataGroupingCell
              {...params}
              costLoading={costLoading}
              showTreeControls={false}
              style={{paddingTop: 0}}
              displayName={displayName}
            />
          </div>
        );
      },
    }),
    [costLoading, expandedGroups, rootCallId, completeCallDataMap]
  );

  // Handle row clicks including group headers
  const onRowClick = useCallback(
    (params: any) => {
      if (!params?.row) {
        return;
      }

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
    [
      call.callId,
      call.entity,
      call.project,
      call.traceId,
      currentRouter,
      history,
    ]
  );

  // Style the selected call
  const callClass = `.callId-${selectedCall.callId}`;
  const getRowClassName: DataGridProProps['getRowClassName'] = useCallback(
    params => {
      if (!params.row.call) {
        return '';
      }
      const rowCallData = params.row.call as CallSchema;
      return `callId-${rowCallData.callId}`;
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
        const rowIndex =
          apiRef.current.getRowIndexRelativeToVisibleRows(callId);
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
  const isGroupExpandedByDefault: DataGridProProps['isGroupExpandedByDefault'] =
    useCallback(
      node => expandedGroups.has(node.groupingKey?.toString() || ''),
      [expandedGroups]
    );

  // Add getTreeDataPath prop
  const getTreeDataPath: DataGridProProps['getTreeDataPath'] = useCallback(
    row => row.hierarchy || [],
    []
  );

  return (
    <CallTimeline>
      <ErrorBoundary>
        <DataGridPro
          apiRef={apiRef}
          getRowHeight={params => {
            if ('isGroupHeader' in params.model) {
              return 40;
            }
            if ('call' in params.model) {
              return isAICall(params.model.call) ? 112 : 64;
            }
            return 52;
          }}
          columnHeaderHeight={0}
          treeData
          loading={animationBuffer}
          onRowClick={onRowClick}
          rows={animationBuffer ? [] : processedRows}
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

// Export the wrapper instead of the view directly
export {CallTimelineWrapper as CallTimelineView};
