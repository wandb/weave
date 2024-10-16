import React from 'react';

export interface StrippedContentEditableProps {
  className?: string;
  innerRef?: React.Ref<HTMLElement>;
  value: string;
  disabled?: boolean;
  onTempChange?: (tempVal: string) => void;

  onKeyDown?: (event: React.KeyboardEvent) => void;
  onChange: (newVal: string) => void;
  onFocus?: (event: React.FocusEvent<HTMLElement>) => void;
  onBlur?: (event: React.FocusEvent<HTMLElement>) => void;
  onPaste?: (event: React.ClipboardEvent<HTMLElement>) => void;
}

function unescapeString(s: string) {
  const doc = new DOMParser().parseFromString(s, 'text/html');
  return doc.documentElement.textContent ?? '';
}

const StrippedContentEditable: React.FC<
  StrippedContentEditableProps
> = props => {
  const spanRef = React.useRef<HTMLSpanElement>(null);
  React.useEffect(() => {
    if (
      spanRef.current &&
      props.value != null &&
      spanRef.current.textContent !== props.value
    ) {
      spanRef.current.textContent = props.value;
    }
  }, [props.value, spanRef]);
  return (
    <>
      <span
        contentEditable={!props.disabled}
        className={props.className}
        ref={node => {
          if (typeof props.innerRef === 'function') {
            props.innerRef(node);
          } else {
            (props.innerRef as any).current = node;
          }
          (spanRef as any).current = node;
        }}
        onFocus={props.onFocus}
        onPaste={props.onPaste}
        onKeyDown={e => {
          // Pass shift enter through
          if (e.keyCode === 13 && e.shiftKey) {
            e.preventDefault();
          } // enter
          else if (e.keyCode === 13) {
            e.preventDefault();

            window.setTimeout(() => {
              spanRef.current?.blur();
            });
            return;
          }
          props.onKeyDown?.(e);
          const target = e.currentTarget;
          const prevText = target.textContent;
          window.setTimeout(() => {
            if (target.textContent !== prevText) {
              props.onTempChange?.(unescapeString(target.textContent || ''));
            }
          });
        }}
        onBlur={e => {
          props.onBlur?.(e);
        }}
      />
    </>
  );
};
export default StrippedContentEditable;
