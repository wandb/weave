import {
  WEAVE_PRIVATE_PREFIX,
  WEAVE_REF_PREFIX,
} from './pages/wfReactInterface/constants';

const encodeSelect = (part: string): string => {
  const symbols: string[] = ['%', '/', ':'];
  for (const symbol of symbols) {
    part = part.replace(new RegExp(symbol, 'g'), encodeURIComponent(symbol));
  }
  return part;
};

export const makeRefCall = (
  entity: string,
  project: string,
  callId: string
): string => {
  return `${WEAVE_REF_PREFIX}${entity}/${project}/call/${callId}`;
};

export const makeRefObject = (
  entity: string,
  project: string,
  objectType: string,
  objectId: string,
  objectVersion: string,
  alreadyEncodedRefExtra: string | undefined = undefined
): string => {
  let objNameAndVersion = `${encodeSelect(objectId)}:${objectVersion}`;
  if (objectType === 'table') {
    objNameAndVersion = objectVersion;
  }

  let ref = `${WEAVE_REF_PREFIX}${entity}/${project}/${objectType}/${objNameAndVersion}`;
  if (alreadyEncodedRefExtra && alreadyEncodedRefExtra !== '') {
    ref += `/${alreadyEncodedRefExtra}`;
  }
  return ref;
};

export const abbreviateRef = (ref: string): string => {
  return WEAVE_REF_PREFIX + '/...' + ref.slice(-6);
};

export const privateRefToSimpleName = (ref: string) => {
  if (!ref.startsWith(WEAVE_PRIVATE_PREFIX)) {
    throw new Error('Not a private ref');
  }
  const trimmed = ref.replace(`${WEAVE_PRIVATE_PREFIX}//`, '');
  try {
    return decodeURIComponent(trimmed.split('/')[1].split(':')[0]);
  } catch (e) {
    return trimmed;
  }
};
