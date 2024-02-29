/**
 * Display opname:v# for an opVersionRef as we might get from a call.
 */

import React from 'react';

import {opNiceName} from '../common/Links';
import {useWFHooks} from '../wfReactInterface/context';
import {refUriToOpVersionKey} from '../wfReactInterface/utilities';

const useOpVersionText = (
  opVersionRef: string | null,
  spanName: string
): string => {
  const {useOpVersion} = useWFHooks();
  const opVersion = useOpVersion(
    opVersionRef ? refUriToOpVersionKey(opVersionRef) : null
  );
  if (opVersion.result) {
    const {opId, versionIndex} = opVersion.result;
    return `${opId}:v${versionIndex}`;
  }
  return opNiceName(spanName);
};

type OpVersionTextProps = {
  opVersionRef: string | null;
  spanName: string;
};

export const OpVersionText = ({opVersionRef, spanName}: OpVersionTextProps) => {
  const text = useOpVersionText(opVersionRef, spanName);
  return <span>{text}</span>;
};
