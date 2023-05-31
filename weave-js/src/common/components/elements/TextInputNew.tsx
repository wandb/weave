import React, {FC} from 'react';
import {Input as SemanticInput, InputOnChangeData} from 'semantic-ui-react';
import styled from 'styled-components';

type TextInputProps = {
  dataTest: string;
  onChange: (e: React.SyntheticEvent, {value}: InputOnChangeData) => void;
  placeholder?: string;
  value?: string;
};

export const TextInput: FC<TextInputProps> = React.memo(
  ({dataTest, onChange, placeholder, value}) => {
    return (
      <Input
        data-test={dataTest}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
      />
    );
  }
);

const Input = styled(SemanticInput)`
  &&& input {
    border: none;
    padding: 0;
    width: 100%;
    background-color: transparent;
  }
`;
