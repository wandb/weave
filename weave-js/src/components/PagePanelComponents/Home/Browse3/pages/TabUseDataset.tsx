import {Box} from '@mui/material';
import React from 'react';

import {isValidVarName} from '../../../../../core/util/var';
import {parseRef} from '../../../../../react';
import {abbreviateRef} from '../../../../../util/refs';
import {Alert} from '../../../../Alert';
import {CopyableText} from '../../../../CopyableText';
import {DocLink} from './common/Links';
import {
  OBJECT_ATTR_EDGE_NAME,
  TABLE_ID_EDGE_NAME,
} from './wfReactInterface/constants';

type TabUseDatasetProps = {
  name: string;
  uri: string;
  versionIndex: number;
};

const ROW_PATH_PREFIX = `${OBJECT_ATTR_EDGE_NAME}/rows/${TABLE_ID_EDGE_NAME}/`;

export const TabUseDataset = ({
  name,
  uri,
  versionIndex,
}: TabUseDatasetProps) => {
  const ref = parseRef(uri);
  const isParentObject = !ref.artifactRefExtra;
  const isRow = ref.artifactRefExtra?.startsWith(ROW_PATH_PREFIX) ?? false;
  const label = isParentObject ? 'dataset version' : isRow ? 'row' : 'object';
  let pythonName = isValidVarName(name) ? name : 'dataset';
  if (isRow) {
    pythonName += '_row';
  }

  // TODO: Row references are not yet supported, you get:
  //       ValueError: '/' not currently supported in short-form URI
  let long = '';
  if (!isRow && 'projectName' in ref) {
    long = `weave.init('${ref.projectName}')
${pythonName} = weave.ref('${ref.artifactName}:v${versionIndex}').get()`;
  }

  return (
    <Box m={2}>
      <Alert icon="lightbulb-info">
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
          text={`${pythonName} = weave.ref("${abbreviateRef(uri)}").get()`}
          copyText={`${pythonName} = weave.ref("${uri}").get()`}
          tooltipText="Click to copy unabridged string"
        />
        {long && (
          <>
            or
            <CopyableText text={long} />
          </>
        )}
      </Box>
    </Box>
  );
};
