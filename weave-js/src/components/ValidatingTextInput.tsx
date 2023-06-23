import * as globals from '@wandb/weave/common/css/globals.styles';
import React, {
  ChangeEvent,
  FC,
  KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import styled from 'styled-components';

const WIDTH_CHAR_LIMIT = 32;

const Wrapper = styled.div`
  position: relative;
  display: inline-block;
  min-width: 20px;
  height: 20px;
`;

const Input = styled.input`
  position: absolute;
  width: 100%;
  border: none;
  border-radius: 2px;

  &:focus {
    outline: 1px solid ${globals.TEAL};
  }

  &.invalid:focus {
    outline: 1px solid ${globals.RED};
  }
`;

const InvisibleSizerSpan = styled.span`
  visibility: hidden;
  display: inline-block;
  padding: 0 2px;
`;

interface TextInputProps {
  dataTest: string;
  onCommit: (newValue: string) => void;
  validateInput: (value: string) => boolean;
  initialValue?: string;
}

export const ValidatingTextInput: FC<TextInputProps> = ({
  dataTest,
  onCommit,
  validateInput,
  initialValue: initialValueProp,
}) => {
  const [initialValue, setInitialValue] = useState(initialValueProp || '');
  const [internalValue, setInternalValue] = useState(initialValue);
  const [isValid, setIsValid] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    setInternalValue(e.target.value);
  };

  useEffect(() => {
    setIsValid(validateInput(internalValue));
  }, [internalValue, validateInput]);

  const handleBlur = useCallback(() => {
    if (internalValue !== initialValue) {
      if (isValid) {
        setInitialValue(internalValue);
        onCommit(internalValue);
      } else {
        setInternalValue(initialValue);
      }
    }
  }, [internalValue, initialValue, isValid, onCommit]);

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      inputRef.current?.blur();
    }
  };

  return (
    <Wrapper>
      <Input
        ref={inputRef}
        className={isValid ? '' : 'invalid'}
        data-test={dataTest}
        value={internalValue}
        onChange={handleChange}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
      />
      <InvisibleSizerSpan>
        {internalValue.slice(0, WIDTH_CHAR_LIMIT)}
      </InvisibleSizerSpan>
    </Wrapper>
  );
};
