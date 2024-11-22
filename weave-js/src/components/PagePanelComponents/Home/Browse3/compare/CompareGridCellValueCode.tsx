import React from 'react';

import {Browse2OpDefCode} from '../../Browse2/Browse2OpDefCode';

type CompareGridCellValueCodeProps = {
  value: string;
};

export const CompareGridCellValueCode = ({
  value,
}: CompareGridCellValueCodeProps) => {
  // Negative margin used to invert (mostly) the padding that we add to other cell types
  // TODO: For better code layout/dependency management might be better to duplicate
  //       Browse2OpDefCode instead of referencing something in Browse2.
  return (
    <div className="m-[-6px] w-full">
      <Browse2OpDefCode uri={value} maxRowsInView={20} />
    </div>
  );
};
