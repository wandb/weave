import {Box, IconButton} from '@material-ui/core';
import {OpenInNewRounded} from '@mui/icons-material';
import {Typography} from '@mui/material';
import _ from 'lodash';
import React, {FC, useMemo} from 'react';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import {MOON_800} from '../../../../../../common/css/color.styles';
import {parseRef} from '../../../../../../react';
import {SmallRef} from '../../../Browse2/SmallRef';
import {useWeaveflowRouteContext} from '../../context';
import {CallsTable} from '../CallsPage/CallsPage';
import {KeyValueTable} from '../common/KeyValueTable';
import {CallLink, opNiceName} from '../common/Links';
import {CenteredAnimatedLoader} from '../common/Loader';
import {
  CallSchema,
  useCalls,
  useParentCall,
} from '../wfReactInterface/interface';

const Heading = styled.div`
  color: ${MOON_800};
  font-weight: 600;
  display: flex;
  align-items: center;
  padding: 8px 8px 0 8px;
  gap: 4px;
`;
Heading.displayName = 'S.Heading';

export const CallSchemaLink = ({call}: {call: CallSchema}) => {
  const {entity: entityName, project: projectName, callId, spanName} = call;
  return (
    <CallLink
      entityName={entityName}
      projectName={projectName}
      opName={spanName}
      callId={callId}
    />
  );
};

export const CallDetails: FC<{
  call: CallSchema;
}> = ({call}) => {
  const parentCall = useParentCall(call);
  const {inputs, output} = useMemo(
    () => getDisplayInputsAndOutput(call),
    [call]
  );

  let parentInfo = null;
  if (parentCall.result) {
    parentInfo = <CallSchemaLink call={parentCall.result} />;
  }

  const childCalls = useCalls(call.entity, call.project, {
    parentIds: [call.callId],
  });

  const {singularChildCalls, multipleChildCallOpRefs} = useMemo(
    () => callGrouping(!childCalls.loading ? childCalls.result ?? [] : []),
    [childCalls.loading, childCalls.result]
  );
  const {baseRouter} = useWeaveflowRouteContext();
  const history = useHistory();

  return (
    <Box
      style={{
        width: '100%',
        height: '100%',
        overflowX: 'hidden',
        overflowY: 'auto',
        // padding: 2,
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
        {multipleChildCallOpRefs.map(ref => (
          <Box
            key={ref}
            sx={{
              flex: '0 0 auto',
              height: '500px',
              maxHeight: '95%',
              p: 2,
              display: 'flex',
              flexDirection: 'column',
            }}>
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'row',
                flex: '0 0 auto',
                alignItems: 'center',
                justifyContent: 'space-between',
                height: '50px',
              }}>
              <Typography sx={{display: 'flex', gap: 1}}>
                Table of <SmallRef objRef={parseRef(ref)} wfTable="OpVersion" />{' '}
                child calls
              </Typography>
              <IconButton
                onClick={() => {
                  history.push(
                    baseRouter.callsUIUrl(call.entity, call.project, {
                      opVersionRefs: [ref],
                      parentId: call.callId,
                    })
                  );
                }}>
                <OpenInNewRounded />
              </IconButton>
            </Box>{' '}
            <Box
              sx={{
                flex: '1 1 auto',
                overflow: 'hidden',
              }}>
              <CallsTable
                hideControls
                ioColumnsOnly
                initialFilter={{
                  opVersionRefs: [ref],
                  parentId: call.callId,
                }}
                entity={call.entity}
                project={call.project}
              />
            </Box>
          </Box>
        ))}
        {childCalls.loading && <CenteredAnimatedLoader />}
        {singularChildCalls.length > 0 && (
          <Box
            sx={{
              flex: '0 0 auto',
            }}>
            {multipleChildCallOpRefs.length === 0 ? (
              <Typography pl={1}>Child calls</Typography>
            ) : (
              <Typography pl={1}>Singular child calls</Typography>
            )}
            {singularChildCalls.map(c => (
              <Box
                key={c.callId}
                sx={{
                  flex: '0 0 auto',
                  p: 2,
                }}>
                <KeyValueTable
                  headerTitle={opNiceName(c.spanName)}
                  data={getDisplayInputsAndOutput(c)}
                />
              </Box>
            ))}
          </Box>
        )}
      </Box>
    </Box>
  );
};

const getDisplayInputsAndOutput = (call: CallSchema) => {
  const span = call.rawSpan;
  const inputKeys =
    span.inputs._keys ??
    Object.entries(span.inputs)
      .filter(([k, c]) => c != null && !k.startsWith('_'))
      .map(([k, c]) => k);
  const inputs = _.fromPairs(inputKeys.map(k => [k, span.inputs[k]]));

  const callOutput = span.output ?? {};
  const outputKeys =
    callOutput._keys ??
    Object.entries(callOutput)
      .filter(([k, c]) => c != null && (k === '_result' || !k.startsWith('_')))
      .map(([k, c]) => k);
  const output = _.fromPairs(outputKeys.map(k => [k, callOutput[k]]));
  return {inputs, output};
};

const callGrouping = (childCalls: CallSchema[]) => {
  const sortedChildCalls = childCalls.sort(
    (a, b) => a.rawSpan.start_time_ms - b.rawSpan.start_time_ms
  );

  const childCallOpCounts: {[ref: string]: number} = {};
  sortedChildCalls.forEach(c => {
    const opRef = c.opVersionRef;
    if (opRef == null) {
      return;
    }
    childCallOpCounts[opRef] = (childCallOpCounts[opRef] ?? 0) + 1;
  });

  const singularChildCalls = sortedChildCalls.filter(c => {
    const opRef = c.opVersionRef;
    if (opRef == null) {
      return true;
    }
    return childCallOpCounts[opRef] === 1;
  });

  const multipleChildCallOpRefs = Object.keys(childCallOpCounts).filter(
    ref => childCallOpCounts[ref] > 1
  );

  return {singularChildCalls, multipleChildCallOpRefs};
};
