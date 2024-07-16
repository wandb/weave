import _ from 'lodash';
import React, {useCallback} from 'react';

import {TextField} from '../../../../Form/TextField';

type TextValueProps = {
  value: string;
  onSetValue: (value: string) => void;
};

export const TextValue = ({value, onSetValue}: TextValueProps) => {
  const throttledSetValue = _.throttle(
    val => {
      onSetValue(val);
    },
    500,
    {trailing: true}
  );

  const onChange = useCallback(throttledSetValue, [onSetValue]);

  return (
    <div style={{minWidth: 200}}>
      <TextField value={value} onChange={onChange} />
    </div>
  );
};
