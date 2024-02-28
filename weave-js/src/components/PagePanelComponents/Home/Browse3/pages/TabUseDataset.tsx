import {Alert, Box} from '@mui/material';
import React from 'react';

import {isValidVarName} from '../../../../../core/util/var';
import {parseRef} from '../../../../../react';
import {CopyableText} from '../../../../CopyableText';
import {DocLink} from './common/Links';

type TabUseDatasetProps = {
  name: string;
  uri: string;
};

const ROW_PATH_PREFIX = 'atr/rows/ndx/';

export const TabUseDataset = ({name, uri}: TabUseDatasetProps) => {
  const ref = parseRef(uri);
  const isParentObject = !ref.artifactRefExtra;
  const isRow = ref.artifactRefExtra?.startsWith(ROW_PATH_PREFIX) ?? false;
  const label = isParentObject ? 'dataset version' : isRow ? 'row' : 'object';
  let pythonName = isValidVarName(name) ? name : 'dataset';
  if (isRow) {
    pythonName +=
      '_row' + ref.artifactRefExtra?.substring(ROW_PATH_PREFIX.length);
  }

  return (
    <Box m={2}>
      <Alert severity="info" variant="outlined">
        See{' '}
        <DocLink
          path="guides/tracking/objects#getting-an-object-back"
          text="Weave docs on refs"
        />{' '}
        and <DocLink path="guides/core-types/datasets" text="datasets" /> for
        more information.
      </Alert>

      <Box mt={2}>
        The ref for this {label} is:
        <CopyableText text={uri} />
      </Box>
      <Box mt={2}>
        Use the following code to retrieve this {label}:
        <CopyableText
          text={`${pythonName} = weave.ref("<ref_uri>").get()`}
          copyText={`${pythonName} = weave.ref("${uri}").get()`}
        />
      </Box>
    </Box>
  );
};
