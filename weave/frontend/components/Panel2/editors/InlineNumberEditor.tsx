import * as S from './InlineNumberEditor.styles';
import * as QueryEditorStyles from '../ExpressionEditor.styles';
import {Popup} from 'semantic-ui-react';

import React from 'react';
import makeComp from '@wandb/common/util/profiler';

interface InlineNumberEditorProps {
  value: number;
  min: number;
  max: number;
  extraSuggestor?: JSX.Element;
  autofocus?: boolean;
  defaultCursorPos?: number;
  onKeyDown?(event: React.KeyboardEvent): void;
  onFocus?(e: React.FocusEvent<HTMLElement>): void;
  onBlur?(): void;
  setValue(val: number): void;
  onBufferChange?(val: string): void;
}

const InlineNumberEditor: React.FC<InlineNumberEditorProps> = makeComp(
  props => {
    const [open, setOpen] = React.useState(false);
    const ref = React.useRef<HTMLSpanElement>(null);
    React.useEffect(() => {
      if (props.autofocus) {
        ref.current?.focus();
      }
    }, [props.autofocus]);
    let editor = (
      <QueryEditorStyles.ElementSpan elementType="node" spellCheck="false">
        <S.InlineNumberContentEditable
          innerRef={ref}
          float
          onKeyDown={props.onKeyDown}
          value={props.value}
          onFocus={e => {
            setOpen(true);
            if (props.defaultCursorPos != null) {
              const tag = ref.current!;
              const setpos = document.createRange();
              const set = window.getSelection();
              setpos.setStart(
                tag.childNodes[0],

                // if the cursor position is negative, we want to start at the end
                props.defaultCursorPos < 0
                  ? tag.childNodes[0].textContent?.length || 10000000
                  : props.defaultCursorPos
              );
              setpos.collapse(true);
              set?.removeAllRanges();
              set?.addRange(setpos);
            } else {
              // setTimeout(() => {
              //   document.execCommand('selectAll');
              // }, 1);
            }
            props.onFocus?.(e);
          }}
          onTempChange={v => {
            props.onBufferChange?.(v);
          }}
          onBlur={() => {
            setOpen(false);
            props.onBlur?.();
          }}
          onChange={v => {
            if (v !== props.value) {
              props.setValue(v);
            }
          }}></S.InlineNumberContentEditable>
      </QueryEditorStyles.ElementSpan>
    );
    if (props.extraSuggestor != null) {
      editor = (
        <Popup
          open={open}
          position="bottom right"
          content={props.extraSuggestor}
          trigger={editor}
        />
      );
    }
    return editor;
  },
  {id: 'InlineNumberEditor'}
);

export default InlineNumberEditor;
