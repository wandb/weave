import {Box} from '@mui/material';
import React from 'react';

import {isValidVarName} from '../../../../../core/util/var';
import {abbreviateRef} from '../../../../../util/refs';
import {Alert} from '../../../../Alert';
import {CopyableText} from '../../../../CopyableText';
import {DocLink} from './common/Links';

type TabUseObjectProps = {
  name: string;
  uri: string;
};

export const TabUseObject = ({name, uri}: TabUseObjectProps) => {
  const pythonName = isValidVarName(name) ? name : 'obj';
  return (
    <Box m={2}>
      <Alert icon="lightbulb-info">
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
          text={`${pythonName} = weave.ref("${abbreviateRef(uri)}").get()`}
          copyText={`${pythonName} = weave.ref("${uri}").get()`}
          tooltipText="Click to copy unabridged string"
        />
      </Box>
    </Box>
  );
};
