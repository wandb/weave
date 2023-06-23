// This creates and manages the Slate editor for the WeaveExpression component.
import React, {FC, useEffect, useMemo, useRef} from 'react';
import {createEditor, Editor} from 'slate';
import {ReactEditor, withReact} from 'slate-react';
import {withHistory} from 'slate-history';
import {ID} from '@wandb/weave/core';
import {
  GenericProvider,
  useGenericContext,
} from '@wandb/weave/panel/WeaveExpression/contexts/GenericProvider';
import {WeaveExpressionProps} from '@wandb/weave/panel/WeaveExpression/WeaveExpression';
import {usePropsContext} from '@wandb/weave/panel/WeaveExpression/contexts/PropsProvider';
import {CustomRange} from '../../../../custom-slate';

export type SlateEditorProviderInput = Pick<WeaveExpressionProps, 'onMount'>;

interface SlateEditorProviderOutput {
  isFocused: boolean;
  isEmpty: boolean;
  // TODO: revisit the CustomRange type. import is weird, what's ../../../../custom-slate?
  activeNodeRange: CustomRange | null | undefined;
  slateEditorId: string;
  slateEditor: Editor;
}

export const SlateEditorProvider: FC = ({children}) => {
  const {slateEditorProviderInput} = usePropsContext();
  const contextValue: SlateEditorProviderOutput = useSlateEditor(
    slateEditorProviderInput
  );
  return (
    <GenericProvider<SlateEditorProviderOutput>
      value={contextValue}
      displayName="SlateEditorContext">
      {children}
    </GenericProvider>
  );
};

export const useSlateEditorContext = () =>
  useGenericContext<SlateEditorProviderOutput>({
    displayName: 'SlateEditorContext',
  });

const useSlateEditor = (input?: SlateEditorProviderInput) => {
  const {onMount} = input || {};
  // const {stack} = usePanelContext();

  // Create a new Slate editor instance
  const editor = withReact(withHistory(createEditor())); // as any))
  const slateEditor = useRef(editor).current;
  // TODO: do we still need IDs? probably
  const slateEditorId = useRef(ID()).current;

  useEffect(() => {
    console.log('useSlateEditor onMount');
    onMount?.(slateEditor);
  }, [onMount, slateEditor]);
  // const point = {path: [0, 0], offset: 0};
  // slateEditor.selection = {anchor: point, focus: point};
  Editor.normalize(editor, {force: true});

  // const {isValid, isTruncated, tsRoot, onChange} = useWeaveExpressionState({
  //   props,
  //   slateEditor, // TODO: do we need to pass this in?
  // });
  const isFocused = ReactEditor.isFocused(slateEditor);
  const {activeNodeRange} = slateEditor;

  // TODO: fix this
  const isEmpty = true; // Editor.string(slateEditor, []).trim() === '';
  // TODO: revive this, to get tests passing? or figure out a better way to test
  // Store the editor on the window, so we can modify its state
  // from automation.ts (test automation)
  // useEffect(() => {
  //   window.weaveExpressionEditors[slateEditorId] = {
  //     editor: slateEditor,
  //     // applyPendingExpr: () => {},
  //     // onChange: () => {},
  //     // // TODO: re-enable these, maybe
  //     applyPendingExpr,
  //     onChange: onChangeCallback, // (newValue: any) => onChange(newValue, stack),
  //   };
  //   return () => {
  //     delete window.weaveExpressionEditors[slateEditorId];
  //   };
  // }, [slateEditor, slateEditorId]);

  return useMemo(
    () => ({isFocused, isEmpty, activeNodeRange, slateEditorId, slateEditor}),
    [activeNodeRange, isEmpty, isFocused, slateEditor, slateEditorId]
  );
};
