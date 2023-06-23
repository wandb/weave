// These are the props passed to slate-react's <Editable> component
import React, {FocusEvent, useCallback, useMemo, useState} from 'react';
import classNames from 'classnames';
import {Editor} from 'slate';
import {RenderLeafProps} from 'slate-react';
import {Leaf} from '@wandb/weave/panel/WeaveExpression/leaf';
import {EditableProps} from 'slate-react/dist/components/editable';
import {useSlateEditorContext} from '@wandb/weave/panel/WeaveExpression/contexts/SlateEditorProvider';
import {WeaveExpressionProps} from '@wandb/weave/panel/WeaveExpression/WeaveExpression';
import {useExpressionSuggestionsContext} from '@wandb/weave/panel/WeaveExpression/contexts/ExpressionSuggestionsProvider';
import {usePropsContext} from '@wandb/weave/panel/WeaveExpression/contexts/PropsProvider';
import {usePropsEditableDecorate} from '@wandb/weave/panel/WeaveExpression/hooks/usePropsEditableDecorate';

export type PropsEditableInput = Pick<
  WeaveExpressionProps,
  'onBlur' | 'onFocus' | 'isTruncated'
>;

// Returns props to be passed to the <Editable> component
export const usePropsEditable = () => {
  // const {onBlur: propsOnBlur, onFocus: propsOnFocus} = usePropsContext();
  const {slateEditor} = useSlateEditorContext();
  const x = usePropsContext();
  console.log('=== props context', x);

  const {
    propsEditableInput: {
      onBlur: propsOnBlur,
      onFocus: propsOnFocus,
      isTruncated,
    },
  } = usePropsContext() || {};
  const {isValid} = useExpressionSuggestionsContext();
  const className = classNames('weaveExpressionSlateEditable', {
    isValid,
    isTruncated,
  });
  const decorate = usePropsEditableDecorate();
  // TODO: get this working again!!
  // const {onKeyDown} = useWeaveExpressionHotkeys();

  // Override default copy handler to make sure we're getting
  // the contents we want
  const onCopy = React.useCallback(
    ev => {
      if (slateEditor.selection == null) {
        return;
      }
      const selectedText = Editor.string(slateEditor, slateEditor.selection);
      ev.clipboardData.setData('text/plain', selectedText);
      ev.preventDefault();
    },
    [slateEditor]
  );

  // TODO: move to visibility context, probably
  // TODO: this is def wrong. there's an isFocused somewhere else too
  const [isFocused, setIsFocused] = useState(false);

  const onBlur = useCallback(
    (e: FocusEvent<HTMLInputElement>) => {
      setIsFocused(false);
      propsOnBlur?.();
    },
    [propsOnBlur]
  );
  const onFocus = useCallback(
    (e: FocusEvent<HTMLInputElement>) => {
      setIsFocused(true);
      propsOnFocus?.();
    },
    [propsOnFocus]
  );

  const renderLeaf = useCallback(
    // TODO: figure out the leaf-has-no-children warning
    (leafProps: RenderLeafProps) => <Leaf {...leafProps}></Leaf>,
    []
  );

  return useMemo(
    () =>
      ({
        'data-lpignore': true, // LastPass will mess up typing experience.  Tell it to ignore this input
        className,
        decorate,
        // onKeyDown,
        onCopy,
        // TODO: This causes the page to jump around due to a slate issue. Fix it
        // placeholder={<div>"Weave expression"</div>}
        onBlur,
        onFocus,
        renderLeaf,
        // TODO: figure out why this is needed, move to css
        scrollSelectionIntoView: () => {}, // no-op to disable Slate's default scroll behavior when dragging an overflowed element
        // below suggested by copilot. useful or wrong?
        // spellCheck: false,
        // autoCorrect: false,
        // autoCapitalize: false,
        // autoComplete: 'off',
      } as EditableProps),
    [className, decorate, onBlur, onCopy, onFocus, renderLeaf]
  );
};
