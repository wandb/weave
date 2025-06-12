import {useContext} from 'react';

import {LLMMaxTokensKey} from '../pages/PlaygroundPage/llmMaxTokens';
import logoAlibaba from './logos/icon-alibaba.png';
import logoBAAI from './logos/icon-baai.png';
import logoDeepSeek from './logos/icon-deepseek.png';
import logoIBM from './logos/icon-ibm.png';
import logoMeta from './logos/icon-meta.png';
import logoMicrosoft from './logos/icon-microsoft.png';
import logoMistral from './logos/icon-mistral.png';
import {InferenceContext, InferenceContextType, Model, Source} from './types';

// TODO: Duplicating this from core - move into context?
export const INFERENCE_PATH = '/inference';

export function urlInference(collectionId?: string, modelId?: string): string {
  const parts = [INFERENCE_PATH];
  if (collectionId) {
    parts.push(collectionId);
  }
  if (modelId) {
    parts.push(modelId);
  }
  return parts.join('/');
}

const sourceNameMap: Record<Source, string> = {
  BAAI: 'Beijing Academy of Artificial Intelligence (BAAI)',
  deepseek: 'DeepSeek',
  'deepseek-ai': 'DeepSeek',
  'ibm-granite': 'IBM',
  'meta-llama': 'Meta',
  microsoft: 'Microsoft',
  mistral: 'Mistral',
  mistralai: 'Mistral',
  openai: 'OpenAI',
  Qwen: 'Alibaba',
  xai: 'xAI',
};

const sourceLogoMap: Record<Source, string> = {
  BAAI: 'baai',
  deepseek: 'deepseek',
  'deepseek-ai': 'deepseek',
  'ibm-granite': 'ibm',
  'meta-llama': 'meta',
  microsoft: 'microsoft',
  mistral: 'mistral',
  mistralai: 'mistral',
  openai: 'openai',
  Qwen: 'alibaba',
};

const logoIdToImageMap: Record<string, any> = {
  alibaba: logoAlibaba,
  baai: logoBAAI,
  deepseek: logoDeepSeek,
  ibm: logoIBM,
  meta: logoMeta,
  microsoft: logoMicrosoft,
  mistral: logoMistral,
};

export const getModelSource = (model: Model): Source => {
  return (
    model.source ??
    (model.idHuggingFace ? model.idHuggingFace.split('/')[0] : 'unknown')
  );
};

export const getSourceLogo = (source: Source) => {
  const logoId = sourceLogoMap[source];
  if (!logoId) {
    return null;
  }
  return logoIdToImageMap[logoId] ?? null;
};

export const getModelSourceName = (model: Model) => {
  const source = getModelSource(model);
  return sourceNameMap[source];
};

export const getModelLogo = (model: Model) => {
  const source = getModelSource(model);
  return getSourceLogo(source);
};

export const getModelLabel = (model: Model) => {
  return model.label ?? model.id.split('/').pop();
};

export const getLaunchDateString = (model: Model) => {
  if (model.launchDate) {
    const date = new Date(model.launchDate);
    return date.toLocaleDateString('en-US', {month: 'short', year: 'numeric'});
  }
  return '';
};

const toDollarsPerMillionTokens = (priceCentsPerBillionTokens: number) => {
  const centsPerDollar = 100;
  const milPerBil = 1000;
  return priceCentsPerBillionTokens / (centsPerDollar * milPerBil);
};

const getRoundedPriceString = (price: number) => {
  return Number(Math.round(price * 100) / 100)
    .toFixed(2)
    .replace(/\.?0+$/, '');
};

export const getOnePriceString = (priceCentsPerBillionTokens: number) => {
  // Prefix with literal dollar sign
  return `$${getRoundedPriceString(
    toDollarsPerMillionTokens(priceCentsPerBillionTokens)
  )}`;
};

export const getPriceString = (
  model: Model,
  includeLabel: boolean = true,
  separator: string = '/'
) => {
  // Convert to dollars per million tokens
  const inputPrice = model.priceCentsPerBillionTokensInput;
  const outputPrice = model.priceCentsPerBillionTokensOutput;

  if (inputPrice && outputPrice) {
    return `${getOnePriceString(inputPrice)}${
      includeLabel ? ' input' : ''
    } ${separator} ${getOnePriceString(outputPrice)}${
      includeLabel ? ' output' : ''
    }`;
  } else if (inputPrice) {
    return `${getOnePriceString(inputPrice)}${includeLabel ? ' input' : ''}`;
  } else if (outputPrice) {
    return `${getOnePriceString(outputPrice)}${includeLabel ? ' output' : ''}`;
  }
  return '';
};

const divideAndRound = (
  value: number,
  divisor: number,
  suffix: string,
  fractionDigits?: number
): string => {
  if (divisor === 0) {
    throw new Error('Divisor cannot be zero.');
  }
  const result = value / divisor;
  if (fractionDigits != null) {
    return result.toFixed(fractionDigits) + suffix;
  }
  return result.toString() + suffix;
};

export const getShortNumberString = (
  count: number,
  fractionDigits?: number
): string => {
  if (count >= 1000000000000) {
    return divideAndRound(count, 1000000000000, 'T', fractionDigits);
  } else if (count >= 1000000000) {
    return divideAndRound(count, 1000000000, 'B', fractionDigits);
  } else if (count >= 1000000) {
    return divideAndRound(count, 1000000, 'M', fractionDigits);
  } else if (count >= 1000) {
    return divideAndRound(count, 1000, 'K', fractionDigits);
  }
  return `${count}`;
};

export const getContextWindowString = (model: Model): string => {
  return model.contextWindow != null
    ? getShortNumberString(model.contextWindow)
    : '';
};

export const getModelLicense = (model: Model): string => {
  return model.card?.data?.license ?? 'Unknown';
};

// A default object for when we don't have an inference context.
export const getDefaultInferenceContext = (): InferenceContextType => {
  return {
    isLoggedIn: false,
    isInferenceEnabled: false,
    availabilityMessage: '',
    playgroundEntity: '',
    playgroundProject: '',
    projectExists: false,
    ensureProjectExists: () => Promise.resolve(),
  };
};

export const useInferenceContext = (): InferenceContextType => {
  // TODO: Once we have added provider in core we could throw an error if there is no context.
  const context = useContext(InferenceContext);
  return context ?? getDefaultInferenceContext();
};

export const getPlaygroundModelString = (model: Model): LLMMaxTokensKey => {
  return `coreweave/${model.idPlayground}` as LLMMaxTokensKey;
};
