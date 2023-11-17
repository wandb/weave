import {TextField} from '@mui/material';
import React, {FC, useCallback, useState} from 'react';

interface ObjectValue {
  [key: string]: any;
}

export const ObjectEditor: FC<{
  label: string;
  valueS: string;
  valid: boolean;
  onValueSChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}> = ({label, valueS, valid, onValueSChange}) => {
  return (
    <TextField
      variant="outlined"
      label={label}
      value={valueS}
      InputProps={{
        style: {
          fontFamily: 'monospace',
        },
      }}
      onChange={onValueSChange}
      error={!valid}
      multiline
      fullWidth
      minRows={10}
      maxRows={20}
    />
  );
};

export const useObjectEditorState = (initialValue: {[key: string]: any}) => {
  const [value, setValue] = useState<ObjectValue>(initialValue);

  const [valid, setValid] = useState(true);

  const [valueS, setValueS] = useState<string>(() =>
    JSON.stringify(value, undefined, 2)
  );

  const onValueSChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setValueS(e.target.value);
      try {
        setValue(JSON.parse(e.target.value));
        setValid(true);
      } catch (e) {
        setValid(false);
      }
    },
    []
  );

  return {
    value,
    valid,
    props: {
      valueS,
      valid,
      onValueSChange,
    },
  };
};
