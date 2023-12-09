import {Box, Button, TextField, Typography} from '@mui/material';
import * as globals from '@wandb/weave/common/css/globals.styles';
import React, {FC, useMemo} from 'react';
import {useParams} from 'react-router-dom';

import {Browse2Calls} from './Browse2Calls';
import {Browse2OpDefCode} from './Browse2OpDefCode';
import {useFirstCall, useOpSignature} from './callTreeHooks';
import {Paper} from './CommonLib';
import {makeObjRefUri} from './CommonLib';
import {Browse2RootObjectVersionItemParams} from './CommonLib';
import {useQuery} from './CommonLib';

export const Browse2OpDefPage: FC = () => {
  const params = useParams<Browse2RootObjectVersionItemParams>();
  return <Browse2OpDefComponent params={params} />;
};

export const Browse2OpDefComponent: FC<{
  params: Browse2RootObjectVersionItemParams;
}> = ({params}) => {
  const uri = makeObjRefUri(params);
  const query = useQuery();
  const filters = useMemo(() => {
    return {
      opUris: [uri],
      inputUris: query.getAll('inputUri'),
    };
  }, [query, uri]);
  const streamId = useMemo(
    () => ({
      entityName: params.entity,
      projectName: params.project,
      streamName: 'stream',
    }),
    [params.entity, params.project]
  );

  const firstCall = useFirstCall(streamId, uri);
  const opSignature = useOpSignature(streamId, uri);

  return (
    <div>
      <Box mb={2}>
        <Browse2Calls streamId={streamId} filters={filters} />
      </Box>
      <Box mb={2}>
        <Paper>
          <Typography variant="h6" gutterBottom>
            Code
          </Typography>
          <Browse2OpDefCode uri={uri} />
        </Paper>
      </Box>
      <Box mb={2}>
        <Paper>
          <Typography variant="h6" gutterBottom>
            Call Op
          </Typography>
          <Box sx={{width: 400}}>
            {opSignature.result != null &&
              Object.keys(opSignature.result.inputTypes).map(k => (
                <Box key={k} mb={2}>
                  <TextField
                    label={k}
                    fullWidth
                    value={
                      firstCall.result != null
                        ? firstCall.result.inputs[k]
                        : undefined
                    }
                  />
                </Box>
              ))}
          </Box>
          <Box pt={1}>
            <Button
              variant="outlined"
              sx={{backgroundColor: globals.lightYellow}}>
              Execute
            </Button>
          </Box>
        </Paper>
      </Box>
    </div>
  );
};
