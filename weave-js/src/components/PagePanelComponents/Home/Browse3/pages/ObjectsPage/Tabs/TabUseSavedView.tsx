import {Box} from '@mui/material';
import React from 'react';

import {isValidVarName} from '../../../../../../../core/util/var';
import {abbreviateRef} from '../../../../../../../util/refs';
import {CopyableText} from '../../../../../../CopyableText';
import {DocLink} from '../../common/Links';
import {TabUseBanner} from '../../common/TabUseBanner';

type TabUseSavedViewProps = {
  name: string;
  uri: string;
};

export const TabUseSavedView = ({name, uri}: TabUseSavedViewProps) => {
  const pythonName = isValidVarName(name) ? name : 'obj';
  return (
    <Box className="text-sm">
      <TabUseBanner>
        See{' '}
        <DocLink
          path="guides/tracking/objects#getting-an-object-back"
          text="Weave docs on refs"
        />{' '}
        for more information.
      </TabUseBanner>

      <Box mt={2}>
        The ref for this saved view version is:
        <CopyableText text={uri} />
      </Box>
      <Box mt={2}>
        Use the following code to retrieve this saved view version:
        <CopyableText
          language="python"
          text={`${pythonName} = weave.SavedView.load("${abbreviateRef(uri)}")`}
          copyText={`${pythonName} = weave.SavedView.load("${uri}")`}
          tooltipText="Click to copy unabridged string"
        />
      </Box>
    </Box>
  );
};
