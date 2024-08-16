import React from 'react';

import {TextField} from '../../../../Form/TextField';

type TextValueProps = {
  value: string;
  onSetValue: (value: string) => void;
};

export const TextValue = ({value, onSetValue}: TextValueProps) => {
  // TODO: Need to debounce the value change.
  return (
    <div className="min-w-[200px]">
      <TextField value={value} onChange={onSetValue} />
    </div>
  );
};
