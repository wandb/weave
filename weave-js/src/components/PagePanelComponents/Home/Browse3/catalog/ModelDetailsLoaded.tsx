import copyToClipboard from 'copy-to-clipboard';
import React, {useCallback, useState} from 'react';
import {Link} from 'react-router-dom';
import {toast} from 'react-toastify';

import {Button} from '../../../../Button';
import {CodeEditor} from '../../../../CodeEditor';
import {Icon} from '../../../../Icon';
import {ToggleButtonGroup} from '../../../../ToggleButtonGroup';
import {DetailTile} from './DetailTile';
import {Modalities} from './Modalities';
import {Model} from './types';
import {getModelLabel} from './util';

type ModelDetailsLoadedProps = {
  model: Model;
};

const CODE_EXAMPLES: Record<string, string> = {
  Python: `
import openai
import weave

# Set a custom base URL
client = openai.OpenAI(
    base_url='https://your-custom-endpoint.com/v1'
)

# Make a call using the client
response = client.chat.completions.create(
    model="{model_id}",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me a joke."}
    ]
)

print(response.choices[0].message['content'])`,
  TypeScript: `
import OpenAI from 'openai';

const openai = new OpenAI({
  baseURL: 'https://your-custom-endpoint.com/v1',
});

async function getJoke() {
  const response = await openai.chat.completions.create({
    model: '{model_id}',
    messages: [
      { role: 'system', content: 'You are a helpful assistant.' },
      { role: 'user', content: 'Tell me a joke.' },
    ],
  });

  console.log(response.choices[0].message?.content);
}

getJoke().catch(console.error);
`,
  Curl: `
  curl https://your-custom-endpoint.com/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer your-api-key" \\
  -d '{
    "model": "{model_id}",
    "messages": [
      { "role": "system", "content": "You are a helpful assistant." },
      { "role": "user", "content": "Tell me a joke." }
    ]
  }'
  `,
};
const CODE_LANGUAGE_MAP: Record<string, string> = {
  Python: 'python',
  TypeScript: 'typescript',
  Curl: 'shell',
};

export const ModelDetailsLoaded = ({model}: ModelDetailsLoadedProps) => {
  const [selectedLanguage, setSelectedLanguage] = useState('Python');

  const label = getModelLabel(model);

  let codeExample = CODE_EXAMPLES[selectedLanguage] ?? '';
  codeExample = codeExample.trim();
  codeExample = codeExample.replace('{model_id}', model.id);

  const onClickCopy = useCallback(() => {
    copyToClipboard(codeExample);
    toast.success('Copied to clipboard');
  }, [codeExample]);

  return (
    <div className="px-32 py-24">
      <div className="flex items-start">
        <div className="flex flex-grow flex-col">
          <div className="text-sm font-semibold">
            <Link to="/catalog" className="flex items-center gap-2">
              <Icon width={16} height={16} name="back" /> Model catalog
            </Link>
          </div>
          <div>
            <div className="flex items-center gap-8">
              <div className="text-2xl">{label}</div>
              {model.modalities && <Modalities modalities={model.modalities} />}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-8">
          <Button size="large" variant="secondary">
            Evaluate model
          </Button>
          <Button size="large">Try in Playground</Button>
        </div>
      </div>
      <div className="mb-8 mt-16 font-semibold">Model overview</div>

      <div className="mb-16 flex gap-10">
        <DetailTile header="Price" footer="Input - Output" />
        <DetailTile header="Context window" />
        <DetailTile header="Parameters" />
        <DetailTile header="Release date" />
        <DetailTile header="Input" />
        <DetailTile header="Output" />
      </div>

      <div className="flex gap-48">
        <div className="text-moon-800">{model.descriptionMedium}</div>
        <div>
          <div className="grid grid-cols-2 gap-8">
            <div className="mb-4 text-sm font-semibold">Provider</div>
            <div className="flex items-center gap-2">
              {/* <img
                  src={getModelLogo(model)}
                  alt={getModelProviderName(model)}
                  className="h-6 w-6"
                />
                <span>{getModelProviderName(model)}</span> */}
            </div>
            <div>
              <div className="mb-4 text-sm font-semibold">Hugging Face</div>
              <div></div>
              {/* <a
                href={model.url_huggingface}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-blue-600 hover:underline">
                <Icon name="external-link" width={16} height={16} />
                View on Hugging Face
              </a> */}
            </div>
          </div>
        </div>
      </div>

      <div className="text-lg font-semibold leading-8">Use this model</div>

      <div className="mb-8 flex items-center">
        <div className="flex-grow">
          <ToggleButtonGroup
            options={[
              {value: 'Python'},
              {value: 'TypeScript'},
              {value: 'Curl'},
            ]}
            value={selectedLanguage}
            size="small"
            onValueChange={setSelectedLanguage}
          />
        </div>
        <div>
          <Button variant="ghost" icon="copy" onClick={onClickCopy} />
        </div>
      </div>
      <div>
        <CodeEditor
          value={codeExample}
          language={CODE_LANGUAGE_MAP[selectedLanguage]}
          readOnly
          handleMouseWheel
          alwaysConsumeMouseWheel={false}
          // wrapLines={wrapLines}
        />
      </div>
    </div>
  );
};
