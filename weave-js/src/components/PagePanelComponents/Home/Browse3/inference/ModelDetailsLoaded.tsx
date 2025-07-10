import copyToClipboard from 'copy-to-clipboard';
import React, {useCallback, useState} from 'react';
import {useHistory} from 'react-router-dom';
import {toast} from 'react-toastify';

import {TargetBlank} from '../../../../../common/util/links';
import {Button} from '../../../../Button';
import {CodeEditor} from '../../../../CodeEditor';
import {Icon} from '../../../../Icon';
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
  getParameterCountString,
  getPriceString,
  INFERENCE_PATH,
} from './util';

type ModelDetailsLoadedProps = {
  model: Model;
  inferenceContext: InferenceContextType;
};

const BASE_URL_QA = 'https://infr.cw4637-staging.coreweave.app/v1';
const BASE_URL_PROD = 'https://api.inference.wandb.ai/v1';
const BASE_URL =
  window.location.hostname === 'qa.wandb.ai' ? BASE_URL_QA : BASE_URL_PROD;

// # Enable HTTPX debugging
// import logging
// logging.basicConfig(level=logging.DEBUG)

// TODO: Should probably pull this out into a central place
const CODE_EXAMPLES_CHAT: Record<string, string> = {
  Python: `
import openai
import weave

# Weave autopatches OpenAI to log LLM calls to W&B
weave.init("<team>/<project>")

client = openai.OpenAI(
    # The custom base URL points to W&B Inference
    base_url='${BASE_URL}',

    # Get your API key from ${window.location.origin}/authorize
    # Consider setting it in the environment as OPENAI_API_KEY instead for safety
    api_key="<your-apikey>",

    # Team and project are required for usage tracking
    project="<team>/<project>",
)

response = client.chat.completions.create(
    model="{model_id}",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me a joke."}
    ],
)

print(response.choices[0].message.content)`,
  TypeScript: `
import OpenAI from "openai";

// Initialize OpenAI client with API key, base URL, and custom headers
const client = new OpenAI({
  apiKey: "<your-apikey>", // 🔐 Replace with your actual API key
  baseURL: "${BASE_URL}", // 🔁 Replace with your actual base URL
  defaultHeaders: {
    "OpenAI-Project": "<team>/<project>",
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
  -H "Authorization: Bearer <your-apikey>" \\
  -H "OpenAI-Project: <team>/<project>" \\
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
  const hasPlayground =
    !!model.idPlayground && inferenceContext.isInferenceEnabled;
  const tooltipPlayground = hasPlayground
    ? undefined
    : inferenceContext.availabilityMessage;

  const hasPrice =
    (model.priceCentsPerBillionTokensInput ?? 0) > 0 ||
    (model.priceCentsPerBillionTokensOutput ?? 0) > 0;

  const hasParameterCounts =
    (model.parameterCountTotal ?? 0) > 0 ||
    (model.parameterCountActive ?? 0) > 0;

  const codeExamples =
    model.apiStyle === 'embedding'
      ? CODE_EXAMPLES_EMBEDDING
      : CODE_EXAMPLES_CHAT;
  let codeExample = codeExamples[selectedLanguage] ?? '';
  codeExample = codeExample.trim();
  if (model.idPlayground) {
    codeExample = codeExample.replace('{model_id}', model.idPlayground);
  }

  const onClickCopyModelId = useCallback(() => {
    copyToClipboard(model.idPlayground ?? '');
    toast('Copied to clipboard', {
      position: 'bottom-right',
    });
  }, [model.idPlayground]);

  const onClickCopyCode = useCallback(() => {
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
          {model.idPlayground && (
            <Button
              size="large"
              icon="copy"
              variant="secondary"
              onClick={onClickCopyModelId}
              tooltip="Copy model ID to clipboard">
              {model.idPlayground}
            </Button>
          )}
          <Button
            size="large"
            onClick={onOpenPlayground}
            disabled={!hasPlayground}
            tooltip={tooltipPlayground}>
            Try in Playground
          </Button>
        </div>
      </div>
      <div className="mb-8 mt-16 text-lg font-semibold">Model overview</div>

      <div className="mb-16 flex flex-wrap gap-10">
        {hasPrice && (
          <DetailTile
            header="Price"
            footer="Input - Output"
            tooltip="Price per million tokens">
            <div className="text-xl font-semibold">
              {getPriceString(model, false, '-')}
            </div>
          </DetailTile>
        )}
        {hasParameterCounts && (
          <DetailTile
            header="Parameters"
            footer={model.parameterCountActive ? 'Active - Total' : 'Total'}>
            <div className="text-xl font-semibold">
              {getParameterCountString(model)}
            </div>
          </DetailTile>
        )}
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
            {model.license && (
              <>
                <div className="flex items-center">
                  <Icon name="courthouse-license" width={18} height={18} />
                </div>
                <div className="flex items-center">
                  {getModelLicense(model)}
                </div>
              </>
            )}
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

      {hasPlayground && (
        <>
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
              <Button
                variant="ghost"
                icon="copy"
                onClick={onClickCopyCode}
                tooltip="Copy code sample to clipboard"
              />
            </div>
          </div>
          <div className="[&_.monaco-editor]:!absolute">
            <CodeEditor
              value={codeExample}
              language={CODE_LANGUAGE_MAP[selectedLanguage]}
              readOnly
              handleMouseWheel
              alwaysConsumeMouseWheel={false}
            />
          </div>
        </>
      )}
    </div>
  );
};
