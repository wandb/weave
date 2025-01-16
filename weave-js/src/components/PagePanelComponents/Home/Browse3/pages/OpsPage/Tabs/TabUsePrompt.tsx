import {Box} from '@mui/material';
import React from 'react';

import {isValidVarName} from '../../../../../../../core/util/var';
import {parseRef} from '../../../../../../../react';
import {abbreviateRef} from '../../../../../../../util/refs';
import {Alert} from '../../../../../../Alert';
import {CopyableText} from '../../../../../../CopyableText';
import {DocLink} from '../../common/Links';

type Data = Record<string, any>;

type TabUsePromptProps = {
  name: string;
  uri: string;
  entityName: string;
  projectName: string;
  data: Data;
};

export const TabUsePrompt = ({
  name,
  uri,
  entityName,
  projectName,
  data,
}: TabUsePromptProps) => {
  const pythonName = isValidVarName(name) ? name : 'prompt';
  const ref = parseRef(uri);
  const isParentObject = !ref.artifactRefExtra;
  const label = isParentObject ? 'prompt version' : 'prompt';

  return (
    <Box className="text-sm">
      <Alert icon="lightbulb-info">
        See{' '}
        <DocLink
          path="guides/tracking/objects#getting-an-object-back"
          text="Weave docs on refs"
        />{' '}
        and <DocLink path="guides/core-types/prompts" text="prompts" /> for more
        information.
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
      </Box>
    </Box>
  );
};
