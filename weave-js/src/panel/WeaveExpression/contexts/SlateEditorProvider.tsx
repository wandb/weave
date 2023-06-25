// This creates and manages the Slate editor for the WeaveExpression component.
import React, {FC, useEffect, useMemo, useRef, useState} from 'react';
import {createEditor, Editor, Node as SlateNode} from 'slate';
import {ReactEditor, withReact} from 'slate-react';
import {withHistory} from 'slate-history';
import {ID, voidNode} from '@wandb/weave/core';
import {
  GenericProvider,
  useGenericContext,
} from '@wandb/weave/panel/WeaveExpression/contexts/GenericProvider';
import {WeaveExpressionProps} from '@wandb/weave/panel/WeaveExpression/WeaveExpression';
import {usePropsContext} from '@wandb/weave/panel/WeaveExpression/contexts/PropsProvider';
import {CustomRange} from '../../../../custom-slate';
import {useWeaveContext} from '@wandb/weave/context';

export type SlateEditorProviderInput = Pick<WeaveExpressionProps, 'onMount'>;

interface SlateEditorProviderOutput {
  isFocused: boolean;
  isEmpty: boolean;
  // TODO: revisit the CustomRange type. import is weird, what's ../../../../custom-slate?
  activeNodeRange: CustomRange | null | undefined;
  slateEditorId: string;
  slateEditor: Editor;
  slateValue: SlateNode[];

  setSlateValue(value: SlateNode[]): void;
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

const useSlateEditor = (
  input?: SlateEditorProviderInput
): SlateEditorProviderOutput => {
  const {onMount} = input || {};
  // const {stack} = usePanelContext();

  // Create a new Slate editor instance
  const editor = withReact(withHistory(createEditor())); // as any))
  // TODO: not sure if useRef is the right thing. maybe useSlateStatic or useSlateWithV
  // TODO: ok actually i think this is wrong. we need to pass slate editor into the <Slate> component
  // and then just useSlate to get the editor. don't need to store editor here.
  const slateEditor = useRef(editor).current;
  const slateEditorId = useRef(ID()).current;
  const editorText = useSlateEditorText();
  const [slateValue, setSlateValue] = useState<SlateNode[]>([
    {
      type: 'paragraph',
      children: [{text: editorText}],
    },
  ]);

  useEffect(() => {
    onMount?.(slateEditor);
  }, [onMount, slateEditor]);
  // TODO: what's all this stuff? do we need to force normalize?
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

  // TODO: split up this memo
  return useMemo(
    () => ({
      isFocused,
      isEmpty,
      activeNodeRange,
      slateEditorId,
      slateEditor,
      slateValue,
      setSlateValue,
    }),
    [
      activeNodeRange,
      isEmpty,
      isFocused,
      slateEditor,
      slateEditorId,
      slateValue,
    ]
  );
};

// TODO: is this dumb? or maybe move elsewhere?
export const useSlateEditorText = () => {
  // const {expToString} = useWeaveContext(); // should exptostring even be in weavecontext?
  const weave = useWeaveContext();
  const {expression} = usePropsContext();
  // const {expToString} = weave;

  // TODO: working on this, expTostring not working.
  // hypothesis: maybe because before we were passing in an already-constructed weave object into useWeaveExpressionContext and that no longer is the case?
  // console.log({expression});
  // TODO: probably move editorText to context
  // TODO: is this the editor text? looks like we're getting it from props expr, not editor
  return weave.expToString(expression ?? voidNode(), null);
};
