import React from 'react';
import styled from 'styled-components';

import * as globals from '../css/globals.styles';
import {GLOBAL_COLORS} from '../util/colors';

export interface AutoCompletingInputProps {
  className?: string;
  options: Array<number | string>;
  value?: number | string;
  disabled?: boolean;
  onSelect(val: number | string): void;
  onBlur?(event: React.FocusEvent<HTMLInputElement>): void;
  onFocus?(event: React.FocusEvent<HTMLInputElement>): void;
}

const BlankInput = styled.input`
  border: none;
  width: 100%;
  padding: 4px 6px;
  height: 28px;
  font-family: ${globals.fontName};
  min-width: 0;
  &:focus {
    outline: none;
    box-shadow: 0 0 3px 2px ${GLOBAL_COLORS.primary.toString()};
  }
`;

const AutoCompletingInput: React.FC<AutoCompletingInputProps> = props => {
  const [tempVal, setTempVal] = React.useState<number | string | undefined>();
  const inputRef = React.useRef<HTMLInputElement>(null);
  const lastKeyDown = React.useRef<number>(0);
  React.useEffect(() => {
    setTempVal(props.value);
  }, [props.value]);
  return (
    <BlankInput
      className={props.className}
      ref={inputRef}
      value={tempVal}
      onKeyDown={e => {
        lastKeyDown.current = e.keyCode;
        if (e.keyCode === 13 /* enter */) {
          inputRef.current?.blur();
          return;
        }
        if (e.keyCode === 27 /* esc */) {
          inputRef.current?.blur();
          return;
        }
      }}
      onInput={e => {
        const val = e.currentTarget.value;
        let match: string | number | null = null;
        if (val != null && val.length > 0) {
          for (const opt of props.options) {
            if (
              opt.toString().slice(0, val.length).toLowerCase() ===
              val.toLowerCase()
            ) {
              match = opt;
              break;
            }
          }
        }
        if (match == null || lastKeyDown.current === 8 /* backspace */) {
          setTempVal(val);
        } else {
          setTempVal(match);
          window.setTimeout(() => {
            if (val != null && match != null) {
              inputRef.current?.setSelectionRange(
                val.length,
                match.toString().length
              );
            }
          });
        }
      }}
      onFocus={e => {
        inputRef.current?.select();
        props.onFocus?.(e);
      }}
      onBlur={e => {
        if (
          lastKeyDown.current !== 27 /* esc */ &&
          tempVal != null &&
          props.options.indexOf(tempVal) !== -1
        ) {
          props.onSelect(tempVal);
        } else {
          setTempVal(props.value);
        }
        props.onBlur?.(e);
      }}
    />
  );
};

export default AutoCompletingInput;
