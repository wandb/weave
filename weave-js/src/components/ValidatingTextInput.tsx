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

const Wrapper = styled.div`
  position: relative;
  display: inline-block;
  min-width: 20px;
  height: 20px;
`;

const InputWrapper = styled.div`
  position: absolute;
  width: 100%;
  display: flex;
  align-items: center;
`;

const Input = styled.input`
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

const Ellipsis = styled.span`
  flex-shrink: 0;
`;

const InvisibleSizerSpan = styled.span`
  visibility: hidden;
  display: inline-block;
  padding: 0 2px;
`;

type ValidatingTextInputProps = {
  dataTest: string;
  onCommit: (newValue: string) => void;
  validateInput: (value: string) => boolean;
  initialValue?: string;
  maxWidth?: number;
  maxLength?: number;
};

export const ValidatingTextInput: FC<ValidatingTextInputProps> = ({
  dataTest,
  onCommit,
  validateInput,
  initialValue: initialValueProp,
  maxWidth,
  maxLength,
}) => {
  const [initialValue, setInitialValue] = useState(initialValueProp ?? '');
  const [internalValue, setInternalValue] = useState(initialValue);
  const [isValid, setIsValid] = useState(true);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const sizerRef = useRef<HTMLSpanElement>(null);
  const [focused, setFocused] = useState(false);
  const [shouldTruncate, setShouldTruncate] = useState(false);

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (maxLength == null) {
      setInternalValue(e.target.value);
      return;
    }
    setInternalValue(e.target.value.slice(0, maxLength));
  };

  useEffect(() => {
    setIsValid(validateInput(internalValue));
  }, [internalValue, validateInput]);

  const handleFocus = useCallback(() => {
    setFocused(true);
  }, []);

  const handleBlur = useCallback(() => {
    setFocused(false);
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

  useEffect(() => {
    // For some reason, this needs the `setTimeout` to work.
    // Otherwise, the wrapper width is not reported correctly.
    setTimeout(() => {
      if (wrapperRef.current == null || sizerRef.current == null) {
        return;
      }

      setShouldTruncate(
        sizerRef.current.offsetWidth > wrapperRef.current.offsetWidth
      );
    });
  });

  return (
    <Wrapper style={{maxWidth}} ref={wrapperRef}>
      <InputWrapper>
        <Input
          ref={inputRef}
          className={isValid ? '' : 'invalid'}
          data-test={dataTest}
          value={internalValue}
          onChange={handleChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
        />
        {!focused && shouldTruncate && <Ellipsis>...</Ellipsis>}
      </InputWrapper>
      <InvisibleSizerSpan ref={sizerRef}>{internalValue}</InvisibleSizerSpan>
    </Wrapper>
  );
};
