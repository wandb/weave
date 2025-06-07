import copyToClipboard from 'copy-to-clipboard';
import React, {useCallback, useState} from 'react';
import {useHistory} from 'react-router-dom';
import {toast} from 'react-toastify';

import {TargetBlank} from '../../../../../common/util/links';
import {Button} from '../../../../Button';
import {CodeEditor} from '../../../../CodeEditor';
import {Icon, IconPrivacyOpen} from '../../../../Icon';
import {ToggleButtonGroup} from '../../../../ToggleButtonGroup';
import {Tooltip} from '../../../../Tooltip';
import {Link} from '../pages/common/Links';
import {DetailTile} from './DetailTile';
import logoHuggingFace from './logos/icon-hugging-face.png';
import {Modalities} from './Modalities';
import {navigateToPlayground} from './navigate';
import {InferenceContextType, Model} from './types';
import {
  getContextWindowString,
  getLaunchDateString,
  getModelLabel,
  getModelLicense,
  getModelLogo,
  getModelSourceName,
  getPriceString,
  getShortNumberString,
  INFERENCE_PATH,
} from './util';

type ModelDetailsLoadedProps = {
  model: Model;
  inferenceContext: InferenceContextType;
};

const BASE_URL = 'https://infr.cw4637-staging.coreweave.app/v1';

// # Enable HTTPX debugging
// import logging
// logging.basicConfig(level=logging.DEBUG)

// TODO: Should probably pull this out into a central place
const CODE_EXAMPLES_CHAT: Record<string, string> = {
  Python: `
import openai
import weave

# Set a custom base URL
client = openai.OpenAI(
    base_url='${BASE_URL}',
    # Generally recommend setting OPENAI_API_KEY in the environment
    api_key="some-key-value"
)

# Make a call using the client
response = client.chat.completions.create(
    model="{model_id}",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me a joke."}
    ],
    extra_headers={
        "OpenAI-Project": "entity1/project1"
    },
)

print(response.choices[0].message.content)`,
  TypeScript: `
import OpenAI from "openai";

// Initialize OpenAI client with API key, base URL, and custom headers
const client = new OpenAI({
  apiKey: "some-key-value", // 🔐 Replace with your actual API key
  baseURL: "${BASE_URL}", // 🔁 Replace with your actual base URL
  defaultHeaders: {
    "OpenAI-Project": "entity1/project1",
  },
});

const response = await client.chat.completions.create({
  model: "{model_id}",
  messages: [
    {
      role: "user",
      content: "Write a one-sentence bedtime story about a unicorn.",
    },
  ],
});

console.log(response.choices[0].message.content);
`,
  Curl: `
  curl ${BASE_URL}/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer some-key-value" \\
  -H "OpenAI-Project: entity1/project1" \\
  -d '{
    "model": "{model_id}",
    "messages": [
      { "role": "system", "content": "You are a helpful assistant." },
      { "role": "user", "content": "Tell me a joke." }
    ]
  }'
  `,
};

const CODE_EXAMPLES_EMBEDDING: Record<string, string> = {
  Python: `from openai import OpenAI
client = OpenAI()

response = client.embeddings.create(
    input="Your text string goes here",
    model="{model_id}"
)

print(response.data[0].embedding)`,
  TypeScript: `import OpenAI from "openai";
const openai = new OpenAI();

const embedding = await openai.embeddings.create({
  model: "{model_id}",
  input: "Your text string goes here",
  encoding_format: "float",
});

console.log(embedding);`,
  Curl: `curl https://api.openai.com/v1/embeddings \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer some-key-value" \\
  -d '{
    "input": "Your text string goes here",
    "model": "{model_id}"
  }'`,
};

const CODE_LANGUAGE_MAP: Record<string, string> = {
  Python: 'python',
  TypeScript: 'typescript',
  Curl: 'shell',
};

export const ModelDetailsLoaded = ({
  model,
  inferenceContext,
}: ModelDetailsLoadedProps) => {
  const [selectedLanguage, setSelectedLanguage] = useState('Python');

  const label = getModelLabel(model);
  const logo = getModelLogo(model);

  const history = useHistory();
  const onOpenPlayground = () => {
    navigateToPlayground(history, model.id, inferenceContext);
  };
  const hasPlayground = !!model.idPlayground && inferenceContext.isLoggedIn;
  const tooltipPlayground = hasPlayground
    ? undefined
    : inferenceContext.isLoggedIn
    ? 'This model is not available in the playground'
    : 'You must be logged in to use the playground';

  const codeExamples =
    model.apiStyle === 'embedding'
      ? CODE_EXAMPLES_EMBEDDING
      : CODE_EXAMPLES_CHAT;
  let codeExample = codeExamples[selectedLanguage] ?? '';
  codeExample = codeExample.trim();
  codeExample = codeExample.replace('{model_id}', model.idPlayground);

  const onClickCopy = useCallback(() => {
    copyToClipboard(codeExample);
    toast.success('Copied to clipboard');
  }, [codeExample]);

  return (
    <div className="px-32 py-24">
      <div className="flex items-start">
        <div className="flex flex-grow flex-col">
          <div className="text-sm font-semibold">
            <Link to={INFERENCE_PATH} className="flex items-center gap-2">
              <Icon width={16} height={16} name="back" /> Inference
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
          <Button
            size="large"
            onClick={onOpenPlayground}
            disabled={!hasPlayground}
            tooltip={tooltipPlayground}>
            Try in Playground
          </Button>
        </div>
      </div>
      <div className="mb-8 mt-16 font-semibold">Model overview</div>

      <div className="mb-16 flex gap-10">
        <Tooltip
          trigger={
            <DetailTile header="Price" footer="Input - Output">
              <div className="text-xl font-semibold">
                {getPriceString(model, false, '-')}
              </div>
            </DetailTile>
          }
          content="Price per million tokens"
        />
        {model.contextWindow && (
          <DetailTile header="Context window">
            <div className="text-xl font-semibold">
              {getContextWindowString(model)}
            </div>
          </DetailTile>
        )}
        {model.launchDate && (
          <DetailTile header="Release date">
            <div className="text-xl font-semibold">
              {getLaunchDateString(model)}
            </div>
          </DetailTile>
        )}
        {model.likesHuggingFace && (
          <DetailTile header="HuggingFace Likes">
            <div className="text-xl font-semibold">
              {getShortNumberString(model.likesHuggingFace, 0)}
            </div>
          </DetailTile>
        )}
        {model.downloadsHuggingFace && (
          <DetailTile header="HuggingFace Downloads">
            <div className="text-xl font-semibold">
              {getShortNumberString(model.downloadsHuggingFace, 0)}
            </div>
          </DetailTile>
        )}
      </div>

      <div className="flex gap-48">
        <div className="min-w-0 flex-1 text-moon-800">
          {model.descriptionMedium}
        </div>
        <div className="shrink-0">
          <div className="grid grid-cols-[18px_1fr] items-center gap-x-[10px] gap-y-[12px]">
            <div className="flex items-center">
              <img width={18} height={18} src={logo} alt="" />
            </div>
            <div className="flex items-center">{getModelSourceName(model)}</div>
            <div className="flex items-center">
              <IconPrivacyOpen width={18} height={18} />
            </div>
            <div className="flex items-center">{getModelLicense(model)}</div>

            {model.supportsFunctionCalling !== undefined && (
              <>
                <div className="flex items-center">
                  <Tooltip
                    trigger={<Icon width={18} height={18} name="code-alt" />}
                    content="Support function calling"
                  />
                </div>
                <div className="flex items-center">
                  {model.supportsFunctionCalling
                    ? 'Has function calling'
                    : 'No function calling'}
                </div>
              </>
            )}
            {model.urlHuggingFace && (
              <>
                <div className="flex items-center">
                  <Tooltip
                    trigger={<img src={logoHuggingFace} alt="" />}
                    content="Open Hugging Face model card"
                  />
                </div>
                <div className="flex items-center">
                  <TargetBlank href={model.urlHuggingFace}>
                    {model.idHuggingFace}
                  </TargetBlank>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="mt-16 text-lg font-semibold leading-8">
        Use this model
      </div>

      <div className="mb-8 flex items-center">
        <div className="flex-grow">
          <ToggleButtonGroup
            options={[
              {value: 'Python'},
              // TODO {value: 'TypeScript'},
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
