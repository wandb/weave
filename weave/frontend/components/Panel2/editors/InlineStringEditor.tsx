import * as S from './InlineStringEditor.styles';
import * as QueryEditorStyles from '../ExpressionEditor.styles';

import React from 'react';
import * as SemanticHacks from '@wandb/common/util/semanticHacks';
import WBSuggester, {
  WBSuggesterOptionFetcher,
} from '@wandb/common/components/elements/WBSuggester';
import makeComp from '@wandb/common/util/profiler';
import {WBMenuOption} from '@wandb/common/components/WBMenu';

interface InlineStringEditorProps {
  value: string;
  disabled?: boolean;
  noQuotes?: boolean;
  extraSuggestor?: JSX.Element;
  autocompleteOptions?: WBMenuOption[] | WBSuggesterOptionFetcher;
  autofocus?: boolean;
  elementType: 'node' | 'op' | 'panelOp';
  dataTest?: string;
  defaultCursorPos?: number;
  contextContent?: React.ReactChild | null;

  highlighted?: number | string | null;
  onChangeHighlighted?: (newHighlight: number | string | null) => void;

  onFocus?(e: React.FocusEvent<HTMLElement>): void;
  onBlur?(): void;
  onKeyDown?(event: React.KeyboardEvent): void;
  setValue(val: string): void;
  onBufferChange?(val: string): void;
}

const InlineStringEditor: React.FC<InlineStringEditorProps> = makeComp(
  props => {
    const ref = React.useRef<HTMLSpanElement>(null);
    const [autocompleterQuery, setAutocompleterQuery] = React.useState('');
    const [autocompleterOpen, setAutocompleterOpen] = React.useState(false);
    React.useEffect(() => {
      if (props.autofocus) {
        ref.current?.focus();
      }
    }, [props.autofocus]);

    const editor = (
      <QueryEditorStyles.ElementSpan
        spellCheck="false"
        elementType={props.elementType}>
        <WBSuggester
          className={SemanticHacks.BLOCK_POPUP_CLICKS_CLASSNAME}
          options={props.autocompleteOptions}
          dataTest={props.dataTest}
          onSelect={v => {
            setAutocompleterOpen(false);
            props.setValue(v as string);
          }}
          query={autocompleterQuery}
          open={autocompleterOpen}
          highlighted={props.highlighted}
          onChangeHighlighted={props.onChangeHighlighted}
          contextContent={props.contextContent}
          onParentScroll={() => setAutocompleterOpen(false)}>
          {({inputRef}) => (
            <S.InlineContentEditable
              innerRef={node => {
                (ref as any).current = node;
                inputRef(node);
              }}
              value={props.value}
              disabled={props.disabled}
              onFocus={e => {
                setAutocompleterOpen(true);
                // Set query to empty so we provide all possible results
                setAutocompleterQuery('');
                // And highlight all
                // setTimeout(() => {
                //   document.execCommand('selectAll');
                // }, 1);

                if (props.defaultCursorPos != null) {
                  const tag = ref.current!;
                  const setpos = document.createRange();
                  const set = window.getSelection();

                  if (tag.childNodes.length > 0) {
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
                  }
                }

                props.onFocus?.(e);
              }}
              onPaste={e => {
                e.preventDefault();
                props.onBufferChange?.(e.clipboardData.getData('text'));
              }}
              onKeyDown={props.onKeyDown}
              onBlur={() => {
                setAutocompleterOpen(false);
                props.onBlur?.();
              }}
              onTempChange={v => {
                setAutocompleterQuery(v);
                setAutocompleterOpen(true);
                props.onBufferChange?.(v);
              }}
              onChange={v => {
                if (props.value !== v) {
                  props.setValue(v);
                }
              }}></S.InlineContentEditable>
          )}
        </WBSuggester>
      </QueryEditorStyles.ElementSpan>
    );

    return (
      <>
        {!props.noQuotes && <span style={{pointerEvents: 'none'}}>"</span>}
        {editor}
        {!props.noQuotes && <span style={{pointerEvents: 'none'}}>"</span>}
      </>
    );
  },
  {id: 'InlineStringEditor'}
);

export default InlineStringEditor;
