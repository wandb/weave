import {Box} from '@material-ui/core';
import {Typography} from '@mui/material';
import _ from 'lodash';
import React, {FC, useContext, useMemo} from 'react';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import {MOON_800} from '../../../../../../common/css/color.styles';
import {Button} from '../../../../../Button';
import {useWeaveflowRouteContext, WeaveflowPeekContext} from '../../context';
import {CallsTable} from '../CallsPage/CallsPage';
import {KeyValueTable} from '../common/KeyValueTable';
import {CallLink, opNiceName} from '../common/Links';
import {CenteredAnimatedLoader} from '../common/Loader';
import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {ButtonOverlay} from './ButtonOverlay';
import {ObjectViewerSection} from './ObjectViewerSection';
import {OpVersionText} from './OpVersionText';

const Heading = styled.div`
  color: ${MOON_800};
  font-weight: 600;
  display: flex;
  align-items: center;
  padding: 8px 8px 0 8px;
  gap: 4px;
`;
Heading.displayName = 'S.Heading';

const MultiCallHeader = styled.div`
  cursor: pointer;
  font-family: Source Sans Pro;
  font-size: 16px;
  font-weight: 600;
  line-height: 32px;
  letter-spacing: 0px;
  text-align: left;
`;
MultiCallHeader.displayName = 'S.MultiCallHeader';

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
  const {useCalls} = useWFHooks();

  const {inputs, output} = useMemo(
    () => getDisplayInputsAndOutput(call),
    [call]
  );

  const childCalls = useCalls(call.entity, call.project, {
    parentIds: [call.callId],
  });

  const {singularChildCalls, multipleChildCallOpRefs} = useMemo(
    () => callGrouping(!childCalls.loading ? childCalls.result ?? [] : []),
    [childCalls.loading, childCalls.result]
  );
  const {baseRouter} = useWeaveflowRouteContext();
  const {isPeeking} = useContext(WeaveflowPeekContext);
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
            <ObjectViewerSection title="Inputs" data={inputs} />
          </Box>
        )}
        {Object.keys(output).length > 0 && (
          <Box
            sx={{
              flex: '0 0 auto',
              p: 2,
            }}>
            <ObjectViewerSection title="Outputs" data={output} />
          </Box>
        )}
        {multipleChildCallOpRefs.map(opVersionRef => {
          const exampleCall = childCalls.result?.find(
            c => c.opVersionRef === opVersionRef
          )!;
          const multipleChildURL = baseRouter.callsUIUrl(
            call.entity,
            call.project,
            {
              opVersionRefs: [opVersionRef],
              parentId: call.callId,
            }
          );
          const onClick = () => {
            history.push(multipleChildURL);
          };

          let callsTable = (
            <CallsTable
              hideControls
              ioColumnsOnly
              initialFilter={{
                opVersionRefs: [opVersionRef],
                parentId: call.callId,
              }}
              entity={call.entity}
              project={call.project}
            />
          );
          if (isPeeking) {
            callsTable = (
              <ButtonOverlay url={multipleChildURL} text="Click to view table">
                {callsTable}
              </ButtonOverlay>
            );
          }

          return (
            <Box
              key={opVersionRef}
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
                <MultiCallHeader onClick={onClick}>
                  Child calls of{' '}
                  <OpVersionText
                    opVersionRef={opVersionRef}
                    spanName={exampleCall.spanName}
                  />
                </MultiCallHeader>
                <Button
                  size="small"
                  variant="secondary"
                  icon="share-export"
                  onClick={onClick}>
                  Go to table
                </Button>
              </Box>
              <Box
                sx={{
                  flex: '1 1 auto',
                  overflow: 'hidden',
                }}>
                {callsTable}
              </Box>
            </Box>
          );
        })}
        {childCalls.loading && <CenteredAnimatedLoader />}
        {/* Disabling display of singular children while we decide if we want them here. */}
        {false && singularChildCalls.length > 0 && (
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

export const processGenericData = (inputs: any) => {
  const callInput = inputs ?? {};
  const inputKeys: string[] =
    callInput._keys ??
    Object.entries(callInput)
      .filter(([k, c]) => c != null && !k.startsWith('_'))
      .map(([k, c]) => k);
  return _.fromPairs(inputKeys.map(k => [k, callInput[k]]));
};

const processOutput = (output: any) => {
  const callOutput = output ?? {};
  const outputKeys: string[] =
    callOutput._keys ??
    Object.entries(callOutput)
      .filter(([k, c]) => c != null && (k === '_result' || !k.startsWith('_')))
      .map(([k, c]) => k);
  return _.fromPairs(outputKeys.map(k => [k, callOutput[k]]));
};

const getDisplayInputsAndOutput = (call: CallSchema) => {
  const span = call.rawSpan;
  const inputs = processGenericData(span.inputs);
  const output = processOutput(span.output);

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
