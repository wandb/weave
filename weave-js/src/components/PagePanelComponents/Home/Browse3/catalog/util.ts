import logoAlibaba from './logos/icon-alibaba.png';
import logoBAAI from './logos/icon-baai.png';
import logoDeepSeek from './logos/icon-deepseek.png';
import logoIBM from './logos/icon-ibm.png';
import logoMeta from './logos/icon-meta.png';
import logoMicrosoft from './logos/icon-microsoft.png';
import logoMistral from './logos/icon-mistral.png';
import {Model, Provider} from './types';

const providerNameMap: Record<Provider, string> = {
  BAAI: 'Beijing Academy of Artificial Intelligence (BAAI)',
  'deepseek-ai': 'DeepSeek',
  'ibm-granite': 'IBM',
  'meta-llama': 'Meta',
  microsoft: 'Microsoft',
  mistralai: 'Mistral',
  Qwen: 'Alibaba',
};

const providerLogoMap: Record<Provider, string> = {
  BAAI: 'baai',
  'deepseek-ai': 'deepseek',
  'ibm-granite': 'ibm',
  'meta-llama': 'meta',
  microsoft: 'microsoft',
  mistralai: 'mistral',
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

export const getModelProvider = (model: Model): Provider => {
  return model.provider ?? model.id.split('/')[0];
};

export const getProviderLogo = (provider: Provider) => {
  const logoId = providerLogoMap[provider];
  if (!logoId) {
    return null;
  }
  return logoIdToImageMap[logoId] ?? null;
};

export const getModelProviderName = (model: Model) => {
  const provider = getModelProvider(model);
  return providerNameMap[provider];
};

export const getModelLogo = (model: Model) => {
  const provider = getModelProvider(model);
  return getProviderLogo(provider);
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

const getOnePriceString = (priceCentsPerBillionTokens: number) => {
  return `$${getRoundedPriceString(
    toDollarsPerMillionTokens(priceCentsPerBillionTokens)
  )}`;
};

export const getPriceString = (model: Model) => {
  // Convert to dollars per million tokens
  const inputPrice = model.priceCentsPerBillionTokensInput;
  const outputPrice = model.priceCentsPerBillionTokensOutput;

  if (inputPrice && outputPrice) {
    return `${getOnePriceString(inputPrice)} input / ${getOnePriceString(
      outputPrice
    )} output`;
  } else if (inputPrice) {
    return `${getOnePriceString(inputPrice)} input`;
  } else if (outputPrice) {
    return `${getOnePriceString(outputPrice)} output`;
  }
  return '';
};

export const getContextWindowString = (contextWindow: number) => {
  if (contextWindow >= 1000000) {
    return `${contextWindow / 1000000}M`;
  } else if (contextWindow >= 1000) {
    return `${contextWindow / 1000}K`;
  }
  return `${contextWindow}`;
};
