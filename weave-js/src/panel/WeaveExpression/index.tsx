import {ID} from '@wandb/weave/core';
import React, {useEffect, useState} from 'react';
import {Ref} from 'semantic-ui-react';
import {createEditor, Editor, Transforms} from 'slate';
import {withHistory} from 'slate-history';
import {ReactEditor, Slate, withReact} from 'slate-react';
import styled from 'styled-components';

import {usePanelContext} from '../../components/Panel2/PanelContext';
import {useWeaveContext} from '../../context';
import {
  useRunButtonVisualState,
  useSuggestionTaker,
  useWeaveDecorate,
  useWeaveExpressionState,
} from './hooks';
import {Leaf} from './leaf';
import * as S from './styles';
import {Suggestions} from './suggestions';
import {WeaveExpressionProps} from './types';
import {trace} from './util';

// We attach some stuff to the window for test automation (see automation.ts)
declare global {
  interface Window {
    SlateLibs: {
      Transforms: typeof Transforms;
      Editor: typeof Editor;
      ReactEditor: typeof ReactEditor;
    };
    weaveExpressionEditors: {
      [editorId: string]: {
        applyPendingExpr: () => void;
        editor: any;
        onChange: (newValue: any) => void;
      };
    };
  }
}

window.SlateLibs = {Transforms, Editor, ReactEditor};
window.weaveExpressionEditors = {};

export const WeaveExpression: React.FC<WeaveExpressionProps> = props => {
  const weave = useWeaveContext();
  const {stack} = usePanelContext();
  const [editor] = useState(() =>
    withReact(withHistory(createEditor() as any))
  );
  const {
    onChange,
    slateValue,
    suggestions,
    tsRoot,
    isValid,
    isBusy,
    applyPendingExpr,
    exprIsModified,
    isFocused,
    onFocus,
    onBlur,
  } = useWeaveExpressionState(props, editor, weave);
  const decorate = useWeaveDecorate(editor, tsRoot);
  const {takeSuggestion, suggestionIndex, setSuggestionIndex} =
    useSuggestionTaker(suggestions, weave, editor);
  const [, forceRender] = useState({});
  const {containerRef, applyButtonRef} = useRunButtonVisualState(
    editor,
    exprIsModified,
    isValid,
    isFocused,
    props.truncate
  );

  // Store the editor on the window, so we can modify its state
  // from automation.ts (test automation)
  const [editorId] = useState(ID());
  useEffect(() => {
    window.weaveExpressionEditors[editorId] = {
      applyPendingExpr,
      editor,
      onChange: (newValue: any) => onChange(newValue, stack),
    };
    return () => {
      delete window.weaveExpressionEditors[editorId];
    };
  }, [applyPendingExpr, editor, editorId, onChange, stack]);

  const [showSuggestions, setShowSuggestions] = useState(
    props.expr?.nodeType === 'void'
  );

  // Wrap onChange so that we reset suggestion index back to top
  // on any interaction
  const onChangeResetSuggestion = React.useCallback(
    newValue => {
      setSuggestionIndex(0);
      onChange(newValue, stack);
    },
    [setSuggestionIndex, onChange, stack]
  );

  // Override default copy handler to make sure we're getting
  // the contents we want
  const copyHandler = React.useCallback(
    ev => {
      const selectedText = Editor.string(editor, editor!.selection!);
      ev.clipboardData.setData('text/plain', selectedText);
      ev.preventDefault();
    },
    [editor]
  );

  // Certain keys have special behavior
  const keyDownHandler = React.useCallback(
    ev => {
      // Pressing a non-printable character like shift is not enough to cancel
      // the suggestion panel suppression.
      const isPrintableCharacter = ev.key.length === 1;
      if (isPrintableCharacter || ev.key === 'Backspace') {
        setShowSuggestions(true);
      }

      if (ev.key === 'Enter' && !ev.shiftKey && !props.liveUpdate) {
        // Apply outstanding changes to expression
        ev.preventDefault();
        ev.stopPropagation();
        if (exprIsModified && isValid && !isBusy) {
          applyPendingExpr();
          forceRender({});
        }
        setShowSuggestions(false);
      } else if (
        ev.key === 'Tab' &&
        !ev.shiftKey &&
        suggestions.items.length > 0
      ) {
        // Apply selected suggestion
        ev.preventDefault();
        ev.stopPropagation();
        takeSuggestion(suggestions.items[suggestionIndex]);
      } else if (ev.key === 'Escape') {
        // Blur the editor, hiding suggestions
        ev.preventDefault();
        ev.stopPropagation();
        ReactEditor.blur(editor);
        forceRender({});
      } else if (
        ev.key === 'ArrowDown' &&
        !ev.shiftKey &&
        suggestions.items.length > 0
      ) {
        // Suggestion cursor down
        ev.preventDefault();
        ev.stopPropagation();
        setSuggestionIndex((suggestionIndex + 1) % suggestions.items.length);
      } else if (
        ev.key === 'ArrowUp' &&
        !ev.shiftKey &&
        suggestions.items.length > 0
      ) {
        // Suggestion cursor up
        ev.preventDefault();
        ev.stopPropagation();
        setSuggestionIndex(
          (suggestions.items.length + suggestionIndex - 1) %
            suggestions.items.length
        );
      }
    },
    [
      props.liveUpdate,
      applyPendingExpr,
      editor,
      exprIsModified,
      isBusy,
      isValid,
      setSuggestionIndex,
      suggestionIndex,
      suggestions,
      takeSuggestion,
    ]
  );

  trace(
    `Render WeaveExpression ${editorId}`,
    props.expr,
    `editor`,
    editor,
    `slateValue`,
    slateValue,
    `exprIsModified`,
    exprIsModified,
    `suggestions`,
    suggestions,
    `isBusy`,
    isBusy
  );

  // Run button placement
  return (
    <Container spellCheck="false">
      <Slate
        editor={editor}
        initialValue={slateValue}
        onChange={onChangeResetSuggestion}>
        <S.EditableContainer
          ref={containerRef}
          data-test="expression-editor-container"
          data-test-ee-id={editorId}
          noBox={props.noBox}>
          <S.WeaveEditable
            // LastPass will mess up typing experience.  Tell it to ignore this input
            data-lpignore
            // This causes the page to jump around due to a slate issue...
            // TODO: fix
            // placeholder={<div>"Weave expression"</div>}
            className={isValid ? 'valid' : 'invalid'}
            onCopy={copyHandler}
            // onMouseDown={mouseDownHandler}
            onKeyDown={keyDownHandler}
            onBlur={onBlur}
            onFocus={onFocus}
            decorate={decorate}
            renderLeaf={leafProps => <Leaf {...leafProps} />}
            style={{overflowWrap: 'anywhere'}}
            scrollSelectionIntoView={() => {}} // no-op to disable Slate's default scroll behavior when dragging an overflowed element
            $truncate={props.truncate}
          />
          {!props.liveUpdate && !props.frozen && (
            <Ref
              innerRef={element =>
                (applyButtonRef.current = element?.ref?.current)
              }>
              <S.ApplyButton
                primary
                size="tiny"
                disabled={!exprIsModified || !isValid || isBusy}
                onMouseDown={(ev: any) => {
                  // Prevent this element from taking focus
                  // otherwise it disappears before the onClick
                  // can register!
                  ev.preventDefault();
                }}
                onClick={applyPendingExpr}>
                Run {isBusy ? '⧗' : '⏎'}
              </S.ApplyButton>
            </Ref>
          )}
        </S.EditableContainer>
        {!props.frozen && (
          <Suggestions
            forceHidden={!showSuggestions}
            {...suggestions}
            suggestionIndex={suggestionIndex}
            setSuggestionIndex={setSuggestionIndex}
          />
        )}
      </Slate>
    </Container>
  );
};

export const focusEditor = (editor: Editor): void => {
  ReactEditor.focus(editor);
  Transforms.select(editor, Editor.end(editor, []));
};

const Container = styled.div`
  width: 100%;
`;
Container.displayName = 'S.Container';
