/**
 * Select objects to diff
 */

import {DiffEditor} from '@monaco-editor/react';
import stringify from 'json-stable-stringify';
import React, {useState} from 'react';
import {DiffMethod} from 'react-diff-viewer';

import {Button} from '../../../../Button';
import {traversed} from '../pages/CallPage/traverse';
import {DiffViewer} from './DiffViewer';
import {ObjectDiff} from './ObjectDiff';

type ObjectDiffSelectorProps = {
  // For particular object types, like calls, we may know the
  // type of a particular path and use that knowledge for better diffing.
  objectType: string;
  diffMode: string;
  setDiffMode: (mode: string) => void;
  left: any;
  right: any;
};

export const ObjectDiffSelector = ({
  objectType,
  diffMode,
  setDiffMode,
  left,
  right,
}: ObjectDiffSelectorProps) => {
  const [sortKeys, setSortKeys] = useState(true);

  // const traversedLeft = traversed(left);
  // const traversedRight = traversed(right);

  const indent = 2;
  const textLeft = sortKeys
    ? stringify(left, {space: indent})
    : JSON.stringify(left, null, indent);
  const textRight = sortKeys
    ? stringify(right, {space: indent})
    : JSON.stringify(right, null, indent);
  return (
    <div className="h-full overflow-auto">
      <div className="min-h-[40px]">
        <Button
          variant="quiet"
          icon="table"
          active={diffMode === 'tree'}
          onClick={() => setDiffMode('tree')}
          tooltip="View differences in an expandable tree"
        />
        <Button
          variant="quiet"
          icon="document"
          active={diffMode === 'unified'}
          onClick={() => setDiffMode('unified')}
          tooltip="View raw objects interleaved"
        />
        <Button
          variant="quiet"
          icon="split"
          active={diffMode === 'split'}
          onClick={() => setDiffMode('split')}
          tooltip="View raw objects side by side"
        />
      </div>
      {diffMode === 'tree' && (
        <ObjectDiff objectType={objectType} left={left} right={right} />
      )}
      {diffMode !== 'tree' && (
        <>
          <div className="w-full overflow-auto text-xs">
            <DiffViewer
              left={textLeft}
              right={textRight}
              splitView={diffMode === 'split'}
              compareMethod={DiffMethod.WORDS}
            />
          </div>
          <DiffEditor
            originalLanguage="json"
            modifiedLanguage="json"
            original={textLeft}
            modified={textRight}
            options={{
              readOnly: true,
              minimap: {enabled: false},
              scrollBeyondLastLine: false,
              padding: {top: 10, bottom: 10},
              scrollbar: {
                alwaysConsumeMouseWheel: false,
              },
              renderSideBySide: diffMode === 'split',
              folding: true,
            }}
          />
        </>
      )}
    </div>
  );
};
