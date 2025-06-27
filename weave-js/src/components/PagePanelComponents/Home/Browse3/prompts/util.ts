import _ from 'lodash';

import {Message, MessagePart, Messages} from '../pages/ChatView/types';

// Extracts placeholders from a given string. Placeholders are defined as text within curly braces.
// Placeholders may be repeated.
export const extractPlaceholdersFromString = (input: string): string[] => {
  const regex = /{([a-zA-Z_][a-zA-Z0-9_]*)}/g;
  const matches: string[] = [];
  let match: RegExpExecArray | null;

  while ((match = regex.exec(input)) !== null) {
    // TODO: Should be more strict about other things that are not valid placeholders,
    //       i.e. Must not be a Python keyword (like for, if, class, etc.)
    matches.push(match[1]);
  }

  return matches;
};

// Extracts placeholders from a MessagePart.
// Placeholders may be repeated.
export const extractPlaceholdersFromMessagePart = (
  part: MessagePart
): string[] => {
  if (_.isString(part)) {
    return extractPlaceholdersFromString(part);
  }
  if (_.isPlainObject(part) && 'content' in part && _.isString(part.content)) {
    return extractPlaceholdersFromString(part.content);
  }
  return [];
};

// Extracts placeholders from a Message.
// Placeholders may be repeated.
export const extractPlaceholdersFromMessage = (message: Message): string[] => {
  if (_.isString(message.content)) {
    return extractPlaceholdersFromString(message.content);
  }
  if (_.isArray(message.content)) {
    return message.content.flatMap(part =>
      extractPlaceholdersFromMessagePart(part)
    );
  }
  return [];
};

// Extract a unique list of placeholders from Messages.
export const extractPlaceholdersFromMessages = (
  messages: Messages
): string[] => {
  const arr = messages.flatMap(message =>
    extractPlaceholdersFromMessage(message)
  );
  return _.uniq(arr);
};

// https://hackersdictionary.com/html/entry/metasyntactic-variable.html
const METASYNTACTIC_VARIABLES = ['foo', 'bar', 'baz', 'qux', 'quux'];

/**
 * Returns the Nth metasyntactic variable in a repeating sequence.
 * After the initial set, names are suffixed with a counter starting at 1.
 */
export const getMetasyntacticVariable = (n: number): string => {
  const baseCount = METASYNTACTIC_VARIABLES.length;
  const index = n % baseCount;
  const cycle = Math.floor(n / baseCount);
  const baseName = METASYNTACTIC_VARIABLES[index];
  return cycle === 0 ? baseName : `${baseName}${cycle}`;
};

export const formatPlaceholdersArgs = (
  placeholders: string[],
  prefix: string
): string => {
  if (placeholders.length === 0) {
    return '';
  }
  if (placeholders.length === 1) {
    return `${placeholders[0]}="${getMetasyntacticVariable(0)}"`;
  }
  return (
    '\n' +
    prefix +
    prefix +
    placeholders
      .map((placeholder, index) => {
        return `${placeholder}="${getMetasyntacticVariable(index)}"`;
      })
      .join(',\n' + prefix + prefix) +
    ',\n' +
    prefix
  );
};
