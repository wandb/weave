import React from 'react';

import {TextField} from '../../../../Form/TextField';

type TextValueProps = {
  value: string;
  onSetValue: (value: string) => void;
  type?: string;
};

export const TextValue = ({value, onSetValue, type}: TextValueProps) => {
  // TODO: Need to debounce the value change.
  return (
    <div className="ml-1 min-w-[200px]">
      <TextField type={type} value={value} onChange={onSetValue} size="small" />
    </div>
  );
};
