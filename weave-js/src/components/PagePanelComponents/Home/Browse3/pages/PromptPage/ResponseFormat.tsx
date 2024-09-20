import './JsonSchemaViewer.css';

import Collapse from '@mui/material/Collapse';
import {JsonSchemaViewer} from '@stoplight/json-schema-viewer';
import React, {useState} from 'react';

import {Icon} from '../../../../../Icon';

type ResponseFormatProps = {
  schema: any;
};

export const ResponseFormat = ({schema}: ResponseFormatProps) => {
  const [open, setOpen] = useState(false);
  const onClick = () => setOpen(!open);
  return (
    <div className="mt-36 rounded-[8px] bg-blue-300/[0.48] px-16 py-8">
      <div
        style={{fontVariantCaps: 'all-small-caps'}}
        className="flex cursor-pointer items-center gap-4"
        onClick={onClick}>
        <Icon
          name={open ? 'chevron-down' : 'chevron-next'}
          width={16}
          height={16}
        />
        Response format
      </div>
      <Collapse in={open}>
        <JsonSchemaViewer
          schema={schema}
          emptyText="No schema defined"
          defaultExpandedDepth={0}
        />
      </Collapse>
      <div></div>
    </div>
  );
};
