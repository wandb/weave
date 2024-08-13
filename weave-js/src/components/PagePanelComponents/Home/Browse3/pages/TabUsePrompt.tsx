import {Box} from '@mui/material';
import React from 'react';

import {isValidVarName} from '../../../../../core/util/var';
import {parseRef} from '../../../../../react';
import {abbreviateRef} from '../../../../../util/refs';
import {Alert} from '../../../../Alert';
import {CopyableText} from '../../../../CopyableText';
import {DocLink} from './common/Links';

type TabUsePromptProps = {
  name: string;
  uri: string;
  projectName: string;
};

export const TabUsePrompt = ({name, uri, projectName}: TabUsePromptProps) => {
  const pythonName = isValidVarName(name) ? name : 'prompt';
  const ref = parseRef(uri);
  const isParentObject = !ref.artifactRefExtra;
  const label = isParentObject ? 'prompt version' : 'prompt';

  const longExample = `import weave
from openai import OpenAI

weave.init("${projectName}")

${pythonName} = weave.ref("${uri}").get()

class MyModel(weave.Model):
  model_name: str
  prompt: weave.Prompt

  @weave.op
  def predict(self, params: dict) -> dict:
      client = OpenAI()
      response = client.chat.completions.create(
          model=self.model_name,
          messages=self.prompt.bind(params),
      )
      result = response.choices[0].message.content
      if result is None:
          raise ValueError("No response from model")
      return result

mymodel = MyModel(model_name="gpt-3.5-turbo", prompt=${pythonName})

# TODO: Params
params = {}
print(mymodel.predict(params))
`;

  return (
    <Box m={2}>
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

      <Box mt={2}>A more complete example:</Box>
      <Box mt={2}>
        <CopyableText
          text={longExample}
          copyText={longExample}
          tooltipText="Click to copy unabridged string"
        />
      </Box>
    </Box>
  );
};
