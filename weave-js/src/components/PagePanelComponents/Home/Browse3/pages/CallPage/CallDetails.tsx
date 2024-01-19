import {Box} from '@material-ui/core';
import _ from 'lodash';
import React, {FC} from 'react';

import {KeyValueTable} from '../common/KeyValueTable';
import {WFCall} from '../wfInterface/types';

export const CallDetails: FC<{
  wfCall: WFCall;
}> = ({wfCall}) => {
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
      </Box>
    </Box>
  );
};
