import {Box} from '@mui/material';
import React from 'react';

import {isValidVarName} from '../../../../../../../core/util/var';
import {abbreviateRef} from '../../../../../../../util/refs';
import {CopyableText} from '../../../../../../CopyableText';
import {DocLink} from '../../common/Links';
import {TabUseBanner} from '../../common/TabUseBanner';

type TabUseOpProps = {
  name: string;
  uri: string;
};

export const TabUseOp = ({name, uri}: TabUseOpProps) => {
  const pythonName = isValidVarName(name) ? name : 'op';

  return (
    <Box className="text-sm">
      <TabUseBanner>
        See <DocLink path="guides/tracking/ops" text="Weave docs on ops" /> for
        more information.
      </TabUseBanner>

      <Box mt={2}>
        The ref for this operation version is:
        <CopyableText text={uri} />
      </Box>
      <Box mt={2}>
        Use the following code to retrieve this operation version:
        <CopyableText
          language="python"
          text={`${pythonName} = weave.ref("${abbreviateRef(uri)}").get()`}
          copyText={`${pythonName} = weave.ref("${uri}").get()`}
          tooltipText="Click to copy unabridged string"
        />
      </Box>
    </Box>
  );
};
