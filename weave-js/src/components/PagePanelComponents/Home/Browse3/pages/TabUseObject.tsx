import {Alert, Box} from '@mui/material';
import React from 'react';

import {CopyableText} from '../../../../CopyableText';
import {DocLink} from './common/Links';

type TabUseObjectProps = {
  name: string;
  uri: string;
};

export const TabUseObject = ({name, uri}: TabUseObjectProps) => {
  return (
    <Box m={2}>
      <Alert severity="info" variant="outlined">
        See{' '}
        <DocLink
          path="guides/tracking/objects#getting-an-object-back"
          text="Weave docs on refs"
        />{' '}
        for more information.
      </Alert>

      <Box mt={2}>
        The ref for this object version is:
        <CopyableText text={uri} />
      </Box>
      <Box mt={2}>
        Use the following code to retrieve this object version:
        <CopyableText
          text={`${name} = weave.ref("<ref_uri>").get()`}
          copyText={`${name} = weave.ref("${uri}").get()`}
        />
      </Box>
    </Box>
  );
};
