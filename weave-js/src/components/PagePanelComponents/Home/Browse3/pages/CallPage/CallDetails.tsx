import Box from '@mui/material/Box';
import _ from 'lodash';
import React, {FC, useContext, useMemo} from 'react';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import {MOON_800} from '../../../../../../common/css/color.styles';
import {Button} from '../../../../../Button';
import {useWeaveflowRouteContext, WeaveflowPeekContext} from '../../context';
import {CustomWeaveTypeProjectContext} from '../../typeViews/CustomWeaveTypeDispatcher';
import {CallsTable} from '../CallsPage/CallsTable';
import {CallLink} from '../common/Links';
import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {ButtonOverlay} from './ButtonOverlay';
import {ExceptionDetails, getExceptionInfo} from './Exceptions';
import {ObjectViewerSection} from './ObjectViewerSection';
import {OpVersionText} from './OpVersionText';

const HEADER_HEIGHT_BUFFER = 60;

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

const TitleRow = styled.div`
  display: flex;
  align-items: center;
  margin-bottom: 4px;
`;
TitleRow.displayName = 'S.TitleRow';

const Title = styled.div`
  flex: 1 1 auto;
  font-family: Source Sans Pro;
  font-size: 16px;
  font-weight: 600;
  line-height: 32px;
  letter-spacing: 0px;
  text-align: left;
`;
Title.displayName = 'S.Title';

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

const ALLOWED_COLUMN_PATTERNS = [
  'op_name',
  'status',
  'inputs.*',
  'output',
  'output.*',
];

export const CallDetails: FC<{
  call: CallSchema;
}> = ({call}) => {
  const {useCalls} = useWFHooks();

  const excInfo = getExceptionInfo(call.rawSpan.exception);

  const {inputs, output} = useMemo(
    () => getDisplayInputsAndOutput(call),
    [call]
  );
  const { attributes, events, links, resource } = useMemo(
    () => getDisplayOtelSpan(call),
    [call]
  );
  const columns = useMemo(() => ['parent_id', 'started_at', 'ended_at'], []);
  const childCalls = useCalls(
    call.entity,
    call.project,
    {
      parentIds: [call.callId],
    },
    undefined,
    undefined,
    undefined,
    undefined,
    columns
  );

  const {multipleChildCallOpRefs} = useMemo(
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
        <Box
          sx={{
            flex: '0 0 auto',
            maxHeight: `calc(100% - ${HEADER_HEIGHT_BUFFER}px)`,
            p: 2,
          }}>
          <CustomWeaveTypeProjectContext.Provider
            value={{
              entity: call.entity,
              project: call.project,
              mode: 'object_viewer',
            }}>
            <ObjectViewerSection title="Inputs" data={inputs} />
          </CustomWeaveTypeProjectContext.Provider>
        </Box>
        <Box
          sx={{
            flex: '0 0 auto',
            maxHeight: `calc(100% - ${
              multipleChildCallOpRefs.length > 0 ? HEADER_HEIGHT_BUFFER : 0
            }px)`,
            p: 2,
          }}>
          {'traceback' in excInfo ? (
            <div style={{overflow: 'auto', height: '100%'}}>
              <TitleRow
                style={{position: 'sticky', top: 0, backgroundColor: 'white'}}>
                <Title>Error</Title>
              </TitleRow>
              <ExceptionDetails exceptionInfo={excInfo} />
            </div>
          ) : (
            <CustomWeaveTypeProjectContext.Provider
              value={{
                entity: call.entity,
                project: call.project,
                mode: 'object_viewer',
              }}>
              <ObjectViewerSection title="Output" data={output} isExpanded />
            </CustomWeaveTypeProjectContext.Provider>
          )}
        </Box>
        <Box
          sx={{
            flex: '0 0 auto',
            maxHeight: `calc(100% - ${
              multipleChildCallOpRefs.length > 0 ? HEADER_HEIGHT_BUFFER : 0
            }px)`,
            p: 2,
          }}>
          {attributes && Object.keys(attributes).length > 0 && (
            <CustomWeaveTypeProjectContext.Provider
              value={{
                entity: call.entity,
                project: call.project,
                mode: 'object_viewer',
              }}>
              <ObjectViewerSection title="OTEL Attributes" data={attributes} isExpanded />
            </CustomWeaveTypeProjectContext.Provider>
          )}
        </Box>
        <Box
          sx={{
            flex: '0 0 auto',
            maxHeight: `calc(100% - ${
              multipleChildCallOpRefs.length > 0 ? HEADER_HEIGHT_BUFFER : 0
            }px)`,
            p: 2,
          }}>
          {events && Object.keys(events).length > 0 && (
            <CustomWeaveTypeProjectContext.Provider
              value={{
                entity: call.entity,
                project: call.project,
                mode: 'object_viewer',
              }}>
              <ObjectViewerSection title="OTEL Events" data={events} isExpanded />
            </CustomWeaveTypeProjectContext.Provider>
          )}
        </Box>
        <Box
          sx={{
            flex: '0 0 auto',
            maxHeight: `calc(100% - ${
              multipleChildCallOpRefs.length > 0 ? HEADER_HEIGHT_BUFFER : 0
            }px)`,
            p: 2,
          }}>
          {links && Object.keys(links).length > 0 && (
            <CustomWeaveTypeProjectContext.Provider
              value={{
                entity: call.entity,
                project: call.project,
                mode: 'object_viewer',
              }}>
              <ObjectViewerSection title="OTEL Links" data={links} isExpanded />
            </CustomWeaveTypeProjectContext.Provider>
          )}
        </Box>
        <Box
          sx={{
            flex: '0 0 auto',
            maxHeight: `calc(100% - ${
              multipleChildCallOpRefs.length > 0 ? HEADER_HEIGHT_BUFFER : 0
            }px)`,
            p: 2,
          }}>
          {resource && Object.keys(resource).length > 0 && (
            <CustomWeaveTypeProjectContext.Provider
              value={{
                entity: call.entity,
                project: call.project,
                mode: 'object_viewer',
              }}>
              <ObjectViewerSection title="OTEL Resource" data={resource} isExpanded />
            </CustomWeaveTypeProjectContext.Provider>
          )}
        </Box>
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
              initialFilter={{
                opVersionRefs: [opVersionRef],
                parentId: call.callId,
              }}
              entity={call.entity}
              project={call.project}
              allowedColumnPatterns={ALLOWED_COLUMN_PATTERNS}
              paginationModel={isPeeking ? {page: 0, pageSize: 10} : undefined}
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
      </Box>
    </Box>
  );
};

const getDisplayOtelSpan = (call: CallSchema) => {
  const span = call.rawSpan;
  const otel_span = span.attributes
    ? span.attributes['otel_span'] ?? {}
    : {};
  const { attributes, events, links, resource } = otel_span;
  return { attributes, events, links, resource }
};

const getDisplayInputsAndOutput = (call: CallSchema) => {
  const span = call.rawSpan;
  const inputKeys =
    span.inputs._keys ??
    Object.keys(span.inputs).filter(k => !k.startsWith('_') || k === '_type');
  const inputs = _.fromPairs(inputKeys.map(k => [k, span.inputs[k]]));

  const callOutput = span.output ?? {};
  const outputKeys =
    callOutput._keys ??
    Object.keys(callOutput).filter(
      k => k === '_result' || !k.startsWith('_') || k === '_type'
    );
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
