import {MessagePart} from '../genai';
import {parseDataUrl} from './parseDataUrl';

export type MediaPart = Extract<MessagePart, {type: 'blob' | 'uri' | 'file'}>;

/**
 * Turn a single image URL into a `blob` (for `data:` URLs, with the
 * base64 payload extracted) or `uri` (for everything else, passed
 * through verbatim).
 */
export function urlToMediaPart(url: string): MediaPart {
  const data = parseDataUrl(url);
  if (data) {
    return {
      type: 'blob',
      mimeType: data.mimeType,
      modality: 'image',
      content: data.payload,
    };
  }

  return {type: 'uri', modality: 'image', uri: url};
}
