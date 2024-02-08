import {Box, Chip, Typography} from '@mui/material';
import * as globals from '@wandb/weave/common/css/globals.styles';
import {isWandbArtifactRef, parseRef} from '@wandb/weave/react';
import React, {FC} from 'react';
import styled from 'styled-components';

import {monthRoundedTime} from '../../../../common/util/time';
import {Call} from './callTree';

const callOpName = (call: Call) => {
  if (!call.name.startsWith('wandb-artifact:')) {
    return call.name;
  }
  const ref = parseRef(call.name);
  if (!isWandbArtifactRef(ref)) {
    return call.name;
  }
  return ref.artifactName;
};
const CallEl = styled.div`
  display: flex;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
  align-items: center;
  cursor: pointer;
`;
export const CallViewSmall: FC<{
  call: Call;
  // selected: boolean;
  onClick?: () => void;
}> = ({call, onClick}) => {
  return (
    <Box mb={1}>
      <Typography component="span">
        <CallEl
          onClick={() => {
            if (onClick) {
              onClick();
            }
          }}>
          <Box mr={1}>
            <Chip
              variant="outlined"
              label={callOpName(call)}
              sx={{
                backgroundColor:
                  call.status_code === 'ERROR' ? globals.warning : undefined,
                maxWidth: '200px',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            />
          </Box>
          <Typography variant="body2" component="span">
            {monthRoundedTime(call.summary.latency_s)}
          </Typography>
        </CallEl>
      </Typography>
    </Box>
  );
};
