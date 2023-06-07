import {ID} from '@wandb/weave/core';
import React, {
  createContext,
  FC,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {Button, Ref} from 'semantic-ui-react';
import {createEditor, Editor, Transforms} from 'slate';
import {withHistory} from 'slate-history';
import {Editable, ReactEditor, Slate, withReact} from 'slate-react';

import {usePanelContext} from '../../components/Panel2/PanelContext';
import {useWeaveContext} from '../../context';
import {useSuggestionTaker, useWeaveDecorate} from './hooks';
import {Leaf} from './leaf';
// import * as S from './styles';
import {Suggestions} from './Suggestions';
import {WeaveExpressionProps} from './types';
import {trace} from './util';
import styled from 'styled-components';
import {fuzzyMatchHighlight} from '@wandb/weave/common/util/fuzzyMatch';
import {useToggle} from '@wandb/weave/hookUtils';
import classNames from 'classnames';
import {
  useWeaveExpressionContext,
  WeaveExpressionContextProvider,
} from '@wandb/weave/panel/WeaveExpression/contexts/WeaveExpressionContext';

import './styles/WeaveExpression.less';

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

export const WeaveExpression = (props: WeaveExpressionProps) => {
  return (
    <WeaveExpressionContextProvider {...props}>
      <WeaveExpressionComp />
    </WeaveExpressionContextProvider>
  );
};
export const WeaveExpressionComp: React.FC<WeaveExpressionProps> = props => {
  // const weave = useWeaveContext();
  // const {stack} = usePanelContext();
  const {editor, slateDecorator, toggleIsDocsPanelVisible} =
    useWeaveExpressionContext();
  const {noBox} = props; // TODO: this seems wrong
  // const {
  //   onChange,
  //   slateValue,
  //   suggestions,
  //   tsRoot,
  //   isValid,
  //   isBusy,
  //   applyPendingExpr,
  //   exprIsModified,
  //   suppressSuggestions,
  //   hideSuggestions,
  //   isFocused,
  //   onFocus,
  //   onBlur,
  // } = useWeaveExpressionState(props, editor, weave);
  const [, forceRender] = useState({});
  // const {containerRef, applyButtonRef} = useRunButtonVisualState(
  //   editor,
  //   exprIsModified,
  //   isValid,
  //   isFocused,
  //   props.isTruncated
  // );

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
    isBusy,
    `suppressSuggestions`,
    suppressSuggestions
  );

  // Run button placement
  return (
    <Container spellCheck="false">
      <Slate
        editor={editor}
        value={slateValue}
        onChange={onChangeResetSuggestion}>
        <div
          className={classNames('weaveExpression', {hasBox: !noBox})}
          ref={containerRef}
          data-test="expression-editor-container"
          data-test-ee-id={editorId}
          // noBox={props.noBox}
        >
          <Editable
            // LastPass will mess up typing experience.  Tell it to ignore this input
            data-lpignore
            // This causes the page to jump around due to a slate issue...
            // TODO: fix
            // placeholder={<div>"Weave expression"</div>}
            className={classNames('weaveExpressionSlateEditable', {
              isValid,
              isTruncated,
            })}
            onCopy={copyHandler}
            onKeyDown={keyDownHandler}
            onBlur={onBlur}
            onFocus={onFocus}
            decorate={slateDecorator}
            renderLeaf={leafProps => <Leaf {...leafProps} />}
            style={{overflowWrap: 'anywhere'}}
            scrollSelectionIntoView={() => {}} // no-op to disable Slate's default scroll behavior when dragging an overflowed element
          />
          {!props.liveUpdate && (
            // <Ref
            //   innerRef={element =>
            //     (applyButtonRef.current = element?.ref?.current)
            //   }>
            <Button
              ref={r => applyButtonRef}
              className="runButton"
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
            </Button>
            // </Ref>
          )}
        </div>
        <Suggestions
          forceHidden={suppressSuggestions || isBusy}
          {...suggestions}
          suggestionIndex={suggestionIndex}
        />
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
Container.displayName = 'Container';
