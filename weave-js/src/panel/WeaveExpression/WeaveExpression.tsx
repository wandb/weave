import React, {useState} from 'react';
import {Editor, Transforms} from 'slate';
import {Editable, ReactEditor, Slate} from 'slate-react';

import classNames from 'classnames';

import './styles/WeaveExpression.less';
import {EditingNode, NodeOrVoidNode} from '@wandb/weave/core';
import {RunExpressionButton} from '@wandb/weave/panel/WeaveExpression/RunExpressionButton';
import {
  SlateEditorProvider,
  useSlateEditorContext,
} from '@wandb/weave/panel/WeaveExpression/contexts/SlateEditorProvider';
import {ExpressionSuggestionsProvider} from '@wandb/weave/panel/WeaveExpression/contexts/ExpressionSuggestionsProvider';
import {PropsProvider} from '@wandb/weave/panel/WeaveExpression/contexts/PropsProvider';
import {usePropsEditable} from '@wandb/weave/panel/WeaveExpression/hooks/usePropsEditable';
import {usePropsSlate} from '@wandb/weave/panel/WeaveExpression/hooks/usePropsSlate';
import {
  DomRefProvider,
  useDomRefContext,
} from '@wandb/weave/panel/WeaveExpression/contexts/DomRefProvider';
import {Suggestions} from '@wandb/weave/panel/WeaveExpression/suggestions';

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
  console.log('CONTEXT ===');
  return (
    <PropsProvider value={props}>
      <DomRefProvider>
        <SlateEditorProvider>
          <ExpressionSuggestionsProvider>
            <WeaveExpressionComp />
          </ExpressionSuggestionsProvider>
        </SlateEditorProvider>
      </DomRefProvider>
    </PropsProvider>
  );
};

export const WeaveExpressionComp: React.FC = () => {
  // const weave = useWeaveContext();
  // const {stack} = usePanelContext();
  console.log('==== weave expression comp ====');
  const {slateEditor, slateEditorId} = useSlateEditorContext();
  const editableComponentProps = usePropsEditable();
  const slateComponentProps = usePropsSlate();
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

  return (
    <div spellCheck="false">
      {/* TODO: ^ move this spellcheck thing elsewhere */}
      <Slate
        editor={slateEditor}
        {...slateComponentProps}
        // TODO: need to get actual slateValue!!
        // value={slateValue}
        // onChange={onChangeResetSuggestion}
      >
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
          <RunExpressionButton />
        </div>
        <Suggestions

        // TODO: re-enable forceHidden?
        // forceHidden={suppressSuggestions || isBusy}
        // {...suggestions}
        // suggestionIndex={suggestionIndex}
        />
      </Slate>
    </div>
  );
};

// TODO: move this somewhere else
export const focusEditor = (editor: Editor): void => {
  ReactEditor.focus(editor);
  Transforms.select(editor, Editor.end(editor, []));
};
