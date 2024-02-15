import {Box} from '@material-ui/core';
import {GridRowSelectionModel} from '@mui/x-data-grid-pro';
import React, {FC, useMemo, useState} from 'react';
import styled from 'styled-components';

import {MOON_800} from '../../../../../../common/css/color.styles';
import {KeyValueTable} from '../common/KeyValueTable';
import {CenteredAnimatedLoader} from '../common/Loader';
import {
  CallSchema,
  useCalls,
  useParentCall,
} from '../wfReactInterface/interface';
import {
  CallSchemaLink,
  ChildCallDetails,
  getDisplayInputsAndOutput,
} from './ChildCallDetails';
import {ChildCallSummaryTable} from './ChildCallSummaryTable';

const Heading = styled.div`
  color: ${MOON_800};
  font-weight: 600;
  display: flex;
  align-items: center;
  padding: 8px 8px 0 8px;
  gap: 4px;
`;
Heading.displayName = 'S.Heading';

const CenterHeading = styled.div`
  color: ${MOON_800};
  font-weight: 700;
  font-size: 16px;
  text-align: center;
  padding: 8px;
`;
CenterHeading.displayName = 'S.CenterHeading';

export const CallDetails: FC<{
  call: CallSchema;
}> = ({call}) => {
  const parentCall = useParentCall(call);
  const {inputs, output} = useMemo(
    () => getDisplayInputsAndOutput(call),
    [call]
  );
  const childCalls = useCalls(call.entity, call.project, {
    parentIds: [call.callId],
  });

  let parentInfo = null;
  if (parentCall.result) {
    parentInfo = <CallSchemaLink call={parentCall.result} />;
  }

  const childCallData = childCalls.result ?? [];

  // TODO: This should probably be kept in URL query state
  const [rowSelection, setRowSelection] = useState<GridRowSelectionModel>([]);

  return (
    <Box
      style={{
        width: '100%',
        height: '100%',
        overflowX: 'hidden',
        overflowY: 'auto',
      }}>
      {parentInfo && <Heading>Called from {parentInfo}</Heading>}
      <Box
        style={{
          width: '100%',
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          gap: 1,
          paddingTop: '8px',
        }}>
        {Object.keys(inputs).length > 0 && (
          <Box
            sx={{
              flex: '0 0 auto',
              p: 2,
            }}>
            <KeyValueTable
              headerTitle="Inputs"
              data={
                // TODO: Consider bringing back openai chat input/output
                inputs
              }
            />
          </Box>
        )}
        {Object.keys(output).length > 0 && (
          <Box
            sx={{
              flex: '0 0 auto',
              p: 2,
            }}>
            <KeyValueTable
              headerTitle="Output"
              data={
                // TODO: Consider bringing back openai chat input/output
                output
              }
            />
          </Box>
        )}
        {childCalls.loading && <CenteredAnimatedLoader />}
        {childCallData.length > 0 && (
          <Box sx={{p: 2}}>
            <CenterHeading>Child Calls</CenterHeading>
            <ChildCallSummaryTable
              parent={call}
              calls={childCallData}
              onSelectionChange={setRowSelection}
            />
          </Box>
        )}
        {rowSelection.map(ref => {
          const selectionCalls = childCallData.filter(
            c => c.opVersionRef === ref
          );
          return (
            <Box key={ref} sx={{px: '8px'}}>
              <ChildCallDetails parent={call} calls={selectionCalls} />
            </Box>
          );
        })}
      </Box>
    </Box>
  );
};
