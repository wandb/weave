import {Box} from '@mui/material';
import _ from 'lodash';
import React from 'react';
import {useHistory} from 'react-router-dom';

import {MOON_800} from '../../../../../../common/css/color.styles';
import {Button} from '../../../../../Button';
import {useWeaveflowRouteContext} from '../../context';
import {CallsTable} from '../CallsPage/CallsPage';
import {KeyValueTable} from '../common/KeyValueTable';
import {CallLink, opNiceName, OpVersionLink} from '../common/Links';
import {
  CallSchema,
  refUriToOpVersionKey,
  useOpVersion,
} from '../wfReactInterface/interface';

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

const OpVersionRefLink = ({call}: {call: CallSchema}) => {
  const opVersion = useOpVersion(
    call.opVersionRef ? refUriToOpVersionKey(call.opVersionRef) : null
  );
  if (opVersion.result) {
    const {opId, versionHash, versionIndex} = opVersion.result;
    return (
      <OpVersionLink
        entityName={call.entity}
        projectName={call.project}
        opName={opId}
        version={versionHash}
        versionIndex={versionIndex}
      />
    );
  }
  return <>{opNiceName(call.spanName)}</>;
};

type ChildCallDetailsProps = {parent: CallSchema; calls: CallSchema[]};
type ChildCallDetailsSingleProps = {call: CallSchema};
type ChildCallDetailsMultipleProps = {parent: CallSchema; calls: CallSchema[]};

export const ChildCallDetails = ({parent, calls}: ChildCallDetailsProps) => {
  if (calls.length === 0) {
    return null;
  }
  if (calls.length === 1) {
    return <ChildCallDetailsSingle call={calls[0]} />;
  }
  return <ChildCallDetailsMultiple parent={parent} calls={calls} />;
};

const ChildCallDetailsSingle = ({call}: ChildCallDetailsSingleProps) => {
  return (
    <Box
      sx={{
        flex: '0 0 auto',
        mt: '16px',
      }}>
      <Box
        color={MOON_800}
        fontWeight="600"
        display="flex"
        sx={{
          flex: '0 0 auto',
          mb: '8px',
        }}>
        <Box mr="4px">Call to</Box>
        <OpVersionRefLink call={call} />
      </Box>
      <KeyValueTable
        headerTitle={<CallSchemaLink call={call} />}
        data={getDisplayInputsAndOutput(call)}
      />
    </Box>
  );
};

const ChildCallDetailsMultiple = ({
  parent,
  calls,
}: ChildCallDetailsMultipleProps) => {
  const history = useHistory();
  const {baseRouter} = useWeaveflowRouteContext();
  const ref = calls[0].opVersionRef!;
  return (
    <Box
      sx={{
        flex: '0 0 auto',
        height: '500px',
        maxHeight: '95%',
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
        <Box
          color={MOON_800}
          fontWeight="600"
          display="flex"
          sx={{
            flex: '0 0 auto',
          }}>
          <Box mr="4px">Calls to</Box>
          <OpVersionRefLink call={calls[0]} />
        </Box>
        <Button
          variant="secondary"
          size="small"
          icon="share-export"
          onClick={() => {
            history.push(
              baseRouter.callsUIUrl(parent.entity, parent.project, {
                opVersionRefs: [ref],
                parentId: parent.callId,
              })
            );
          }}>
          Go to table
        </Button>
      </Box>
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
            parentId: parent.callId,
          }}
          entity={parent.entity}
          project={parent.project}
        />
      </Box>
    </Box>
  );
};

export const getDisplayInputsAndOutput = (call: CallSchema) => {
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
