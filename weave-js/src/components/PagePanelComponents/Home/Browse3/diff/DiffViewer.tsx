import React from 'react';
import ReactDiffViewer, {DiffMethod} from 'react-diff-viewer';

type DiffViewerProps = {
  left: string;
  right: string;
  splitView?: boolean;
  compareMethod?: DiffMethod;
  hideLineNumbers?: boolean;
};

export const DiffViewer = ({
  left,
  right,
  splitView,
  compareMethod,
  hideLineNumbers,
}: DiffViewerProps) => {
  return (
    <div className="flex-auto text-xs">
      <ReactDiffViewer
        oldValue={left}
        newValue={right}
        splitView={splitView}
        compareMethod={compareMethod}
        hideLineNumbers={hideLineNumbers}
      />
    </div>
  );
};
