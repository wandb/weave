import {Box, IconButton} from '@material-ui/core';
import {OpenInNewRounded} from '@mui/icons-material';
import {Typography} from '@mui/material';
import _ from 'lodash';
import React, {FC, useMemo} from 'react';
import {useHistory} from 'react-router-dom';

import {parseRef} from '../../../../../../react';
import {SmallRef} from '../../../Browse2/SmallRef';
import {useWeaveflowRouteContext} from '../../context';
import {CallsTable} from '../CallsPage/CallsPage';
import {KeyValueTable} from '../common/KeyValueTable';
import {opNiceName} from '../common/Links';
import {WFCall} from '../wfInterface/types';

export const CallDetails: FC<{
  wfCall: WFCall;
}> = ({wfCall}) => {
  const {inputs, output} = useMemo(
    () => getDisplayInputsAndOutput(wfCall),
    [wfCall]
  );
  const {singularChildCalls, multipleChildCallOpRefs} = useMemo(
    () => callGrouping(wfCall),
    [wfCall]
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
                    baseRouter.callsUIUrl(wfCall.entity(), wfCall.project(), {
                      opVersionRefs: [ref],
                      parentId: wfCall.callID(),
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
                  parentId: wfCall.callID(),
                }}
                entity={wfCall.entity()}
                project={wfCall.project()}
              />
            </Box>
          </Box>
        ))}
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
                key={c.callID()}
                sx={{
                  flex: '0 0 auto',
                  p: 2,
                }}>
                <KeyValueTable
                  headerTitle={opNiceName(c.spanName())}
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

const getDisplayInputsAndOutput = (wfCall: WFCall) => {
  const call = wfCall.rawCallSpan();
  const inputKeys =
    call.inputs._keys ??
    Object.entries(call.inputs)
      .filter(([k, c]) => c != null && !k.startsWith('_'))
      .map(([k, c]) => k);
  const inputs = _.fromPairs(inputKeys.map(k => [k, call.inputs[k]]));

  const callOutput = call.output ?? {};
  const outputKeys =
    callOutput._keys ??
    Object.entries(callOutput)
      .filter(([k, c]) => c != null && (k === '_result' || !k.startsWith('_')))
      .map(([k, c]) => k);
  const output = _.fromPairs(outputKeys.map(k => [k, callOutput[k]]));
  return {inputs, output};
};

const callGrouping = (wfCall: WFCall) => {
  const sortedChildCalls = wfCall
    .childCalls()
    .sort(
      (a, b) => a.rawCallSpan().start_time_ms - b.rawCallSpan().start_time_ms
    );

  const childCallOpCounts: {[ref: string]: number} = {};
  sortedChildCalls.forEach(c => {
    const opRef = c.opVersion()?.refUri();
    if (opRef === undefined) {
      return;
    }
    childCallOpCounts[opRef] = (childCallOpCounts[opRef] ?? 0) + 1;
  });

  const singularChildCalls = sortedChildCalls.filter(c => {
    const opRef = c.opVersion()?.refUri();
    if (opRef === undefined) {
      return true;
    }
    return childCallOpCounts[opRef] === 1;
  });

  const multipleChildCallOpRefs = Object.keys(childCallOpCounts).filter(
    ref => childCallOpCounts[ref] > 1
  );

  return {singularChildCalls, multipleChildCallOpRefs};
};
