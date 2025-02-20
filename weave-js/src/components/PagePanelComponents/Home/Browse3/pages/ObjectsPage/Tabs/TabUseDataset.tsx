import {Box} from '@mui/material';
import React from 'react';

import {isValidVarName} from '../../../../../../../core/util/var';
import {parseRef} from '../../../../../../../react';
import {abbreviateRef} from '../../../../../../../util/refs';
import {CopyableText} from '../../../../../../CopyableText';
import {DocLink} from '../../common/Links';
import {TabUseBanner} from '../../common/TabUseBanner';
import {
  OBJECT_ATTR_EDGE_NAME,
  TABLE_ID_EDGE_NAME,
} from '../../wfReactInterface/constants';

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
  const versionName = `${name}_v${versionIndex}`;
  let pythonName = isValidVarName(versionName)
    ? versionName
    : `dataset_v${versionIndex}`;
  if (isRow) {
    pythonName += '_row';
  }

  // TODO: Row references are not yet supported, you get:
  //       ValueError: '/' not currently supported in short-form URI
  let long = '';
  let download = '';
  let downloadCopyText = '';
  if (!isRow && 'projectName' in ref) {
    long = `weave.init('${ref.entityName}/${ref.projectName}')
${pythonName} = weave.ref('${ref.artifactName}:v${versionIndex}').get()`;
    download = `${pythonName}.to_pandas().to_csv("${versionName}.csv", index=False)`;
    downloadCopyText = long + '\n' + download;
  }

  return (
    <Box className="text-sm">
      <TabUseBanner>
        See{' '}
        <DocLink
          path="guides/tracking/objects#getting-an-object-back"
          text="Weave docs on refs"
        />{' '}
        and <DocLink path="guides/core-types/datasets" text="datasets" /> for
        more information.
      </TabUseBanner>

      <Box mt={2}>
        The ref for this {label} is:
        <CopyableText text={uri} />
      </Box>
      <Box mt={2}>
        Use the following code to retrieve this {label}:
        <CopyableText
          language="python"
          text={`${pythonName} = weave.ref("${abbreviateRef(uri)}").get()`}
          copyText={`${pythonName} = weave.ref("${uri}").get()`}
          tooltipText="Click to copy unabridged string"
        />
        {long && (
          <>
            <div className="mt-8">or</div>
            <CopyableText language="python" text={long} />
          </>
        )}
        {download && (
          <Box mt={2}>
            For further analysis or export you can convert this {label} to a
            Pandas DataFrame, for example:
            <CopyableText
              language="python"
              text={download}
              copyText={downloadCopyText}
            />
          </Box>
        )}
      </Box>
    </Box>
  );
};
