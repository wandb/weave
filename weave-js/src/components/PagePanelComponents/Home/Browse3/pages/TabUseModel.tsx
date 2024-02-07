import {Alert, Box} from '@mui/material';
import React from 'react';

import {isValidVarName} from '../../../../../core/util/var';
import {CopyableText} from '../../../../CopyableText';
import {DocLink} from './common/Links';

type TabUseModelProps = {
  name: string;
  uri: string;
  projectName: string;
};

export const TabUseModel = ({name, uri, projectName}: TabUseModelProps) => {
  const pythonName = isValidVarName(name) ? name : 'model';
  return (
    <Box m={2}>
      <Alert severity="info" variant="outlined">
        See{' '}
        <DocLink
          path="guides/tracking/objects#getting-an-object-back"
          text="Weave docs on refs"
        />{' '}
        and <DocLink path="guides/core-types/models" text="models" /> for more
        information.
      </Alert>

      <Box mt={2}>
        The ref for this model version is:
        <CopyableText text={uri} />
      </Box>
      <Box mt={2}>
        Use the following code to retrieve this model version:
        <CopyableText
          text={`${pythonName} = weave.ref("<ref_uri>").get()`}
          copyText={`${pythonName} = weave.ref("${uri}").get()`}
        />
      </Box>
      <Box mt={2}>
        To <DocLink path="guides/tools/serve" text="serve this model" /> locally
        with a Swagger UI:
        <CopyableText
          text="weave serve <ref_uri>"
          copyText={`weave serve ${uri}`}
        />
      </Box>
      <Box mt={2}>
        To <DocLink path="guides/tools/deploy" text="deploy this model" /> to
        the cloud run:
        <CopyableText
          text={`weave deploy gcp --project "${projectName}" <ref_uri>`}
          copyText={`weave deploy gcp --project "${projectName}" ${uri}`}
        />
      </Box>
    </Box>
  );
};
