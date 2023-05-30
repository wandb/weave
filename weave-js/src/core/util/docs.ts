import {kebabCase} from 'lodash';

import type {TypeID} from '../model/types';
import {TYPES_WITH_PAGES} from '../model/types';

const TYPE_DOC_URL = 'https://docs.wandb.ai/ref/weave';

export function urlSafeTypeId(typeId: string) {
  // the machine that builds these docs is case-insensitive,
  // so we need to kebab-case every type id or we'll get
  // broken links
  return kebabCase(typeId);
}

// TODO: After we workout how linking and type names work, fill
// this function in with better logic.
export function docType(
  typeId: TypeID,
  options: {plural?: boolean} = {}
): string {
  const plural = options?.plural ?? false;

  let text: string = typeId;

  if (plural) {
    // if there are more cases we should factor this out into a map
    if (text === 'W&B Entity') {
      text = 'W&B Entities';
    } else {
      text += 's';
    }
  }

  if (TYPES_WITH_PAGES.some(t => t === typeId)) {
    return `[${text}](${TYPE_DOC_URL}/${urlSafeTypeId(typeId)})`;
  }

  // Emphasizing types without doc pages so users still know
  // that they're types
  return `_${text}_`;
}
