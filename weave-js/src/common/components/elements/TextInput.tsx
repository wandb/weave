import React, {FC} from 'react';
import {InputOnChangeData} from 'semantic-ui-react';
import {TextInput as TextInputNew} from './TextInputNew';

import * as S from './TextInput.styles';
import {useWeaveShouldUseSidebarConfigStyling} from '../../../context';

interface TextInputProps {
  dataTest: string;
  label: string;
  onChange: (e: React.SyntheticEvent, {value}: InputOnChangeData) => void;
  placeholder?: string;
  sublabel?: string;
  value?: string;
}

export const TextInput: FC<TextInputProps> = React.memo(props => {
  const {dataTest, label, onChange, placeholder, sublabel, value} = props;

  const useSidebarConfigStyling = useWeaveShouldUseSidebarConfigStyling();
  if (useSidebarConfigStyling) {
    return <TextInputNew {...props} />;
  }

  return (
    <>
      <S.Label>
        {label} <S.Sublabel>{sublabel}</S.Sublabel>
      </S.Label>
      <S.Input
        data-test={dataTest}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
      />
    </>
  );
});
