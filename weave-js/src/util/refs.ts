import { WEAVE_REF_PREFIX } from "../components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/constants";

const encodeSelect = (part: string): string => {
  const symbols: string[] = ['%', '/', ':']
  for (const symbol of symbols) {
    part = part.replace(new RegExp(symbol, 'g'), encodeURIComponent(symbol));
  }
  return part;
}

export const makeRefCall = (
  entity: string,
  project: string,
  callId: string
): string => {
  return `${WEAVE_REF_PREFIX}${entity}/${
    project
  }/call/${callId}`;
};

export const makeRefObject = (
  entity: string,
  project: string,
  objectType: string,
  objectId: string,
  objectVersion: string,
  refExtra: string | undefined = undefined
): string => {
  let objNameAndVersion = `${encodeSelect(objectId)}:${objectVersion}`;
  if (objectType === 'table') {
    objNameAndVersion = objectVersion
  }

  let ref = `${WEAVE_REF_PREFIX}${entity}/${
    project
  }/${objectType}/${objNameAndVersion}`;
  if (refExtra && refExtra !== '') {
    ref += `/${refExtra.split('/').map(encodeSelect).join('/')}`;
  }
  return ref;
};

export const abbreviateRef = (ref: string): string => {
  return WEAVE_REF_PREFIX + '/...' + ref.slice(-6);
};
