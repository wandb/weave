import {Box} from '@mui/material';
import React from 'react';

import {isValidVarName} from '../../../../../../../core/util/var';
import {parseRef} from '../../../../../../../react';
import {abbreviateRef} from '../../../../../../../util/refs';
import {CopyableText} from '../../../../../../CopyableText';
import {DocLink} from '../../common/Links';
import {TabUseBanner} from '../../common/TabUseBanner';

type TabUseModelProps = {
  name: string;
  uri: string;
  projectName: string;
};

export const TabUseModel = ({name, uri, projectName}: TabUseModelProps) => {
  const pythonName = isValidVarName(name) ? name : 'model';
  const ref = parseRef(uri);
  const isParentObject = !ref.artifactRefExtra;
  const label = isParentObject ? 'model version' : 'object';

  return (
    <Box className="text-sm">
      <TabUseBanner>
        See{' '}
        <DocLink path="guides/tracking/models" text="Weave docs on models" />{' '}
        for more information.
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
      </Box>
      {/* Temporarily commenting this out until the serve and deploy features are fixed */}
      {/* {isParentObject && (
        <>
          <Box mt={2}>
            To <DocLink path="guides/tools/serve" text="serve this model" />{' '}
            locally with a Swagger UI:
            <CopyableText
              text={`weave serve "${abbreviateRef(uri)}"`}
              copyText={`weave serve "${uri}"`}
              tooltipText="Click to copy unabridged string"
            />
          </Box>
          <Box mt={2}>
            To <DocLink path="guides/tools/deploy" text="deploy this model" />{' '}
            to the cloud run:
            <CopyableText
              text={`weave deploy gcp --project "${projectName}" "${abbreviateRef(
                uri
              )}"`}
              copyText={`weave deploy gcp --project "${projectName}" "${uri}"`}
              tooltipText="Click to copy unabridged string"
            />
          </Box>
        </>
      )} */}
    </Box>
  );
};
