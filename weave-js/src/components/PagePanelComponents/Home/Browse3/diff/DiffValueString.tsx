/**
 * Compare two timestamp values.
 */

import React from 'react';
import {DiffMethod} from 'react-diff-viewer';

import {DiffViewer} from './DiffViewer';

type DiffValueStringProps = {
  left: string;
  right: string;

  compareMethod: DiffMethod;
};

const isOneLine = (str: string): boolean => !str.includes('\n');

export const DiffValueString = ({
  left,
  right,
  compareMethod,
}: DiffValueStringProps) => {
  // TODO: Newer versions support gutterType prop instead.
  const hideLineNumbers = isOneLine(left) && isOneLine(right);

  return (
    <DiffViewer
      left={left}
      right={right}
      compareMethod={compareMethod}
      hideLineNumbers={hideLineNumbers}
    />
  );
};
