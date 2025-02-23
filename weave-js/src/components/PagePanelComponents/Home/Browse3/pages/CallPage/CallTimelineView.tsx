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

// Import the types from CallTraceView
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

type Row = CallRow | SiblingCountRow | HiddenChildrenCountRow;

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

  // Sort rows by start time
  const sortedRows = useMemo(() => {
    const aiCallTypes = [
      'openai.chat.completions.create',
      'anthropic.Messages.create',
      'anthropic.AsyncMessages.create'
    ];

    // Add debug logging
    if (rows.length > 0) {
      const firstCallRow = rows.find(row => 'call' in row) as CallRow;
      if (firstCallRow) {
        console.log('Example call object:', firstCallRow.call);
      }
    }

    return _.sortBy(
      rows.filter(row => {
        if (!('call' in row)) return false; // Only include call rows
        const callRow = row as CallRow;
        return aiCallTypes.includes(callRow.call.spanName) || 
               aiCallTypes.includes(callRow.call.rawSpan.name);
      }),
      row => (row as CallRow).call.rawSpan.start_time_ms
    );
  }, [rows]);

  // Flatten the hierarchy - each call will be at the root level
  const flattenedRows = useMemo(() => {
    return sortedRows.map(row => ({
      ...row,
      hierarchy: [(row as CallRow).call.callId],
    }));
  }, [sortedRows]);

  // Handle row clicks
  const onRowClick: DataGridProProps['onRowClick'] = useCallback(
    params => {
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

  // Custom grouping column definition
  const groupingColDef: DataGridProProps['groupingColDef'] = useMemo(
    () => ({
      headerName: 'Timeline',
      headerAlign: 'center',
      flex: 1,
      display: 'flex',
      renderCell: params => (
        <CustomGridTreeDataGroupingCell
          {...params}
          costLoading={costLoading}
          showTreeControls={false}
        />
      ),
    }),
    [costLoading]
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
          rowHeight={64}
          columnHeaderHeight={0}
          treeData
          loading={animationBuffer}
          onRowClick={onRowClick}
          rows={animationBuffer ? [] : flattenedRows}
          columns={[]}
          getTreeDataPath={getTreeDataPath}
          groupingColDef={groupingColDef}
          getRowClassName={getRowClassName}
          hideFooter
          rowSelection={false}
          sx={sx}
        />
      </ErrorBoundary>
    </CallTimeline>
  );
}; 