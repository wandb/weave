import React from 'react';

import {CodeView} from './CodeView';

type CompareGridCellValueCodeProps = {
  value: string;
};

export const CompareGridCellValueCode = ({
  value,
}: CompareGridCellValueCodeProps) => {
  // Negative margin used to invert (mostly) the padding that we add to other cell types
  return (
    <div className="m-[-6px] w-full">
      <CodeView uri={value} maxLines={20} />
    </div>
  );
};
