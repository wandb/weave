/**
 * Compare two timestamp values.
 */

import {DiffEditor} from '@monaco-editor/react';
import React from 'react';

type DiffValueLongStringProps = {
  left: string;
  right: string;
  renderSideBySide: boolean;
};

export const DiffValueLongString = ({
  left,
  right,
  renderSideBySide,
}: DiffValueLongStringProps) => {
  return (
    <DiffEditor
      original={left}
      modified={right}
      options={{
        readOnly: true,
        minimap: {enabled: false},
        scrollBeyondLastLine: false,
        padding: {top: 10, bottom: 10},
        scrollbar: {
          alwaysConsumeMouseWheel: false,
        },
        lineNumbers: 'off',
        renderSideBySide,
      }}
    />
  );
};
