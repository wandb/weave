import {Box} from '@mui/material';
import React from 'react';

import {isValidVarName} from '../../../../../../../core/util/var';
import {parseRef} from '../../../../../../../react';
import {abbreviateRef} from '../../../../../../../util/refs';
import {Alert} from '../../../../../../Alert';
import {CopyableText} from '../../../../../../CopyableText';
import {
  extractPlaceholdersFromMessages,
  formatPlaceholdersArgs,
} from '../../../prompts/util';
import {DocLink} from '../../common/Links';

type Data = Record<string, any>;

type TabUsePromptProps = {
  name: string;
  uri: string;
  entityName: string;
  projectName: string;
  data: Data;
  versionIndex: number;
};

export const TabUsePrompt = ({
  name,
  uri,
  entityName,
  projectName,
  data,
  versionIndex,
}: TabUsePromptProps) => {
  const pythonName = isValidVarName(name) ? name : 'prompt';
  const ref = parseRef(uri);
  const isParentObject = !ref.artifactRefExtra;
  const label = isParentObject ? 'prompt version' : 'prompt';

  const long = `weave.init('${entityName}/${projectName}')
${pythonName} = weave.get('${name}:v${versionIndex}')`;

  const placeholders = extractPlaceholdersFromMessages(data.messages);
  const inferenceExample = `import weave
client = ${long}
response = client.chat.completions.create(
    model="coreweave/meta-llama/Llama-3.1-8B-Instruct",
    messages=${pythonName}.format(${formatPlaceholdersArgs(
    placeholders,
    '    '
  )}),
)
print(response.choices[0].message.content)
  `;

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
          text={`${pythonName} = weave.get("${abbreviateRef(uri)}")`}
          copyText={`${pythonName} = weave.get("${uri}")`}
          tooltipText="Click to copy unabridged string"
        />
        <div className="mt-8">or</div>
        <CopyableText language="python" text={long} />
      </Box>
      <Box mt={2}>A complete example:</Box>
      <Box mt={2}>
        <CopyableText
          language="python"
          text={inferenceExample}
          copyText={inferenceExample}
        />
      </Box>
    </Box>
  );
};
