import React from 'react';

import {CellValueMarkdown} from '../../../Browse2/CellValueMarkdown';

type MarkdownViewProps = {
  data: {
    val: {
      markup: string;
    };
  };
};

export const MarkdownView = ({data}: MarkdownViewProps) => {
  if (!data.val || !data.val.markup) {
    return null;
  }
  return <CellValueMarkdown value={data.val.markup} />;
};
