import React, {FC, useState} from 'react';
import {Editor, Transforms} from 'slate';
import {Editable, ReactEditor, Slate} from 'slate-react';

import classNames from 'classnames';

import './styles/WeaveExpression.less';
import {EditingNode, NodeOrVoidNode} from '@wandb/weave/core';
import {ExpressionSuggestionsProvider} from '@wandb/weave/panel/WeaveExpression/contexts/ExpressionSuggestionsProvider';
import {PropsProvider} from '@wandb/weave/panel/WeaveExpression/contexts/PropsProvider';
import {usePropsEditable} from '@wandb/weave/panel/WeaveExpression/hooks/usePropsEditable';
import {usePropsSlate} from '@wandb/weave/panel/WeaveExpression/hooks/usePropsSlate';
import {
  DomRefProvider,
  useDomRefContext,
} from '@wandb/weave/panel/WeaveExpression/contexts/DomRefProvider';
import {Suggestions} from '@wandb/weave/panel/WeaveExpression/suggestions';
import {
  ExpressionEditorProvider,
  useExpressionEditorContext,
} from '@wandb/weave/panel/WeaveExpression/contexts/ExpressionEditorProvider';

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

// TODO: move this somewhere else or get rid of it
window.SlateLibs = {Transforms, Editor, ReactEditor};
window.weaveExpressionEditors = {};

export interface WeaveExpressionProps {
  expression?: EditingNode;
  setExpression?: (expr: NodeOrVoidNode) => void;

  noBox?: boolean;

  onMount?: (editor: Editor) => void;
  onFocus?: () => void;
  onBlur?: () => void;

  isLiveUpdateEnabled?: boolean;
  isTruncated?: boolean; // TODO: search for instances of this variable (previously named 'truncate')
}

export const WeaveExpression = (props: WeaveExpressionProps) => {
  return (
    <PropsProvider value={props}>
      <DomRefProvider>
        <SlateEditor>
          <ExpressionEditorProvider>
            <ExpressionSuggestionsProvider>
              <WeaveExpressionComp />
            </ExpressionSuggestionsProvider>
          </ExpressionEditorProvider>
        </SlateEditor>
      </DomRefProvider>
    </PropsProvider>
  );
};

// TODO: move this
const SlateEditor: FC = ({children}) => {
  const slateComponentProps = usePropsSlate();
  return (
    <div spellCheck="false">
      {/* TODO: ^ move this spellcheck thing elsewhere */}
      <Slate {...slateComponentProps}>{children}</Slate>
    </div>
  );
};

// TODO: rename to ExpressionEditor?
export const WeaveExpressionComp: React.FC = () => {
  // const weave = useWeaveContext();
  // const {stack} = usePanelContext();
  const {slateEditorId} = useExpressionEditorContext();
  const editableComponentProps = usePropsEditable();
  const {expressionEditorDomRef} = useDomRefContext();

  // TODO: figure out what noBox was for and re-enable it
  // const {noBox} = props;
  const noBox = true;
  // TODO: figure out what forceRender was for and re-enable it
  const [, forceRender] = useState({});
  // const {containerRef, applyButtonRef} = useRunButtonVisualState(
  //   editor,
  //   exprIsModified,
  //   isValid,
  //   isFocused,
  //   props.isTruncated
  // );

  // TODO: i don't think we need this
  // // Wrap onChange so that we reset suggestion index back to top
  // // on any interaction
  // const onChangeResetSuggestion = React.useCallback(
  //   newValue => {
  //     setSuggestionIndex(0);
  //     onChange(newValue, stack);
  //   },
  //   [setSuggestionIndex, onChange, stack]
  // );

  // trace(
  //   `Render WeaveExpression ${editorId}`,
  //   props.expr,
  //   `editor`,
  //   editor,
  //   `slateValue`,
  //   slateValue,
  //   `exprIsModified`,
  //   exprIsModified,
  //   `suggestions`,
  //   suggestions,
  //   `isBusy`,
  //   isBusy,
  //   `suppressSuggestions`,
  //   suppressSuggestions
  // );
  console.log(
    '******** editableComponentProps',
    JSON.stringify(editableComponentProps)
  );

  return (
    <>
      {/* TODO: do we need this random div? */}
      <div
        className={classNames('weaveExpression', {hasBox: !noBox})}
        ref={expressionEditorDomRef}
        data-test="expression-editor-container"
        data-test-ee-id={slateEditorId}
        // noBox={props.noBox}
      >
        <Editable
          {...editableComponentProps}

          // className={classNames('weaveExpressionSlateEditable', {
          //   isValid,
          //   isTruncated,
          // })}
          // decorate={slateDecorator}
          // onCopy={copyHandler}
          // onKeyDown={keyDownHandler}
          // onBlur={onBlur}
          // onFocus={onFocus}
          // renderLeaf={leafProps => (
          //   <Leaf {...leafProps} children={undefined} />
          // )}
          // style={{overflowWrap: 'anywhere'}}
        />
        {/* TODO: re-enable this button */}
        {/*<RunExpressionButton />*/}
      </div>
      <Suggestions

      // TODO: re-enable forceHidden?
      // forceHidden={suppressSuggestions || isBusy}
      // {...suggestions}
      // suggestionIndex={suggestionIndex}
      />
    </>
  );
};

// TODO: move this somewhere else
export const focusEditor = (editor: Editor): void => {
  ReactEditor.focus(editor);
  Transforms.select(editor, Editor.end(editor, []));
};
