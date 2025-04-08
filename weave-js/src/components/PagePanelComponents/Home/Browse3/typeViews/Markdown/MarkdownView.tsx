import React from 'react';

import {CellValueMarkdown} from '../../../Browse2/CellValueMarkdown';
import {ValueViewMarkdown} from '../../pages/CallPage/ValueViewMarkdown';

type MarkdownViewProps = {
  mode?: string;
  data: {
    val: {
      markup: string;
    };
  };
};

export const MarkdownView = ({mode, data}: MarkdownViewProps) => {
  if (!data.val || !data.val.markup) {
    return null;
  }
  if (mode === 'object_viewer') {
    return <ValueViewMarkdown value={data.val.markup} />;
  }
  return <CellValueMarkdown value={data.val.markup} />;
};
