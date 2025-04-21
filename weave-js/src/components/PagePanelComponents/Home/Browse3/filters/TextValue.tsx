import React from 'react';

import {TextField} from '../../../../Form/TextField';

type TextValueProps = {
  value: string;
  onSetValue: (value: string) => void;
  type?: string;
  isActive?: boolean;
};

export const TextValue = ({
  value,
  onSetValue,
  type,
  isActive,
}: TextValueProps) => {
  return (
    <div className="ml-1 min-w-[200px]">
      <TextField
        type={type}
        value={value}
        onChange={onSetValue}
        size="small"
        autoFocus={isActive}
      />
    </div>
  );
};
