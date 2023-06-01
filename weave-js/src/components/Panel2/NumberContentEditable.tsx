import React, {RefObject} from 'react';

export interface NumberContentEditableProps {
  className?: string;
  innerRef?: RefObject<HTMLElement>;
  float?: boolean;
  value: number;
  min?: number;
  max?: number;
  onTempChange?: (tempVal: string) => void;
  onKeyDown?: (event: React.KeyboardEvent) => void;
  onChange: (newVal: number) => void;
  onFocus?: (event: React.FocusEvent<HTMLElement>) => void;
  onBlur?: (event: React.FocusEvent<HTMLElement>) => void;
}

function unescapeString(s: string) {
  const doc = new DOMParser().parseFromString(s, 'text/html');
  return doc.documentElement.textContent ?? '';
}

const ENTER = 13;
const NumberContentEditable: React.FC<NumberContentEditableProps> = props => {
  const fallbackRef = React.useRef<HTMLSpanElement>(null);
  const innerRef = props.innerRef ?? fallbackRef;
  React.useEffect(() => {
    if (
      innerRef.current &&
      props.value != null &&
      innerRef.current.innerHTML !== props.value.toString()
    ) {
      innerRef.current.innerHTML = props.value.toString();
    }
  }, [props.value, innerRef]);

  return (
    <span
      ref={innerRef}
      contentEditable
      className={props.className}
      onKeyDown={e => {
        // console.log('keydown', e.keyCode);
        const fieldTextContent = e.currentTarget.textContent;
        if (fieldTextContent == null) {
          console.warn('Invalid state: number input has no text content');
          return;
        }
        if (e.keyCode === ENTER) {
          e.preventDefault();
          innerRef.current?.blur();
          return;
        }
        props.onKeyDown?.(e);
        const target = e.currentTarget;
        const prevHTML = target.innerHTML;
        window.setTimeout(() => {
          if (target.innerHTML !== prevHTML) {
            props.onTempChange?.(unescapeString(target.innerHTML));
          }
        });
      }}
      onFocus={props.onFocus}
      onBlur={e => {
        const html = e.currentTarget.innerHTML;
        if (!isNaN(html as any)) {
          const parsedVal = props.float ? parseFloat(html) : parseInt(html, 10);
          if (!Number.isNaN(parsedVal)) {
            props.onChange(parsedVal);
          }
        }
        if (innerRef.current && props.value != null) {
          innerRef.current.innerHTML = props.value.toString();
        }
        props.onBlur?.(e);
      }}></span>
  );
};
export default NumberContentEditable;
