import {FC, useCallback, useEffect, useMemo} from 'react';
import {Button} from 'semantic-ui-react';
import {Editor, Element} from 'slate';
import {ReactEditor} from 'slate-react';
import {useSlateEditorContext} from '@wandb/weave/panel/WeaveExpression/contexts/SlateEditorProvider';
import {usePropsContext} from '@wandb/weave/panel/WeaveExpression/contexts/PropsProvider';
import {WeaveExpressionProps} from '@wandb/weave/panel/WeaveExpression/WeaveExpression';
import {useExpressionSuggestionsContext} from '@wandb/weave/panel/WeaveExpression/contexts/ExpressionSuggestionsProvider';
import {useDomRefContext} from '@wandb/weave/panel/WeaveExpression/contexts/DomRefProvider';

// TODO: maybe shouldn't use 'Run' in the name, could be confusing.
export const RunExpressionButton: FC = () => {
  const {isDisabled, onClick, onMouseDown} = useRunButton();
  const {isLoading} = useExpressionSuggestionsContext();
  const {runButtonDomRef} = useDomRefContext();

  return (
    <Button
      ref={runButtonDomRef}
      className="runButton"
      primary
      size="tiny"
      disabled={isDisabled}
      onMouseDown={onMouseDown}
      onClick={onClick}>
      Run {isLoading ? '⧗' : '⏎'}
    </Button>
  );
};

export type PropsRunButtonInput = Pick<
  WeaveExpressionProps,
  'isLiveUpdateEnabled' | 'isTruncated'
>;

export const useRunButton = () => {
  // const {slateEditor} = useSlateEditorContext();
  // const {: {isLiveUpdateEnabled, isTruncated}} = usePropsContext();
  const {
    propsRunButtonInput: {isLiveUpdateEnabled, isTruncated},
  } = usePropsContext();
  const {isValid, isDirty, isLoading, acceptSelectedSuggestion} =
    useExpressionSuggestionsContext();
  const {isFocused, isEmpty} = useSlateEditorContext();
  // const {
  //   isFocused,
  //   weaveExpressionState: {isBusy, isDirty, isValid, applyPendingExpr},
  // } = useWeaveExpressionContext();

  const isDisabled = !isDirty || !isValid || isLoading;
  const isHidden =
    isLiveUpdateEnabled ||
    !isValid ||
    (isTruncated && !isFocused) ||
    // TODO: move the editor check to slate hook
    (!isDirty && (!isFocused || isEmpty)); // Editor.string(slateEditor, []).trim() === ''));

  const {naturalLeft, maxLeft, grandOffset} = useRunButtonPosition();

  const style = useMemo(
    () => ({
      display: isHidden ? 'none' : 'inline-block',
      opacity: naturalLeft > maxLeft ? 0.3 : 1.0,
      left: `${Math.min(maxLeft, naturalLeft)}px`,
      top: `${grandOffset - 20}px`,
    }),
    [grandOffset, isHidden, maxLeft, naturalLeft]
  );

  const onMouseDown = useCallback((ev: any) => {
    // Prevent this element from taking focus
    // otherwise it disappears before the onClick
    // can register!
    ev.preventDefault();
  }, []);

  return {
    style,
    onMouseDown,
    onClick: acceptSelectedSuggestion,
    isDisabled,
    // isLoading,
  };
};

// (window as any).Ed = Editor;
export const useRunButtonPosition = () => {
  const {slateEditor} = useSlateEditorContext();
  const {expressionEditorDomRef, runButtonDomRef} = useDomRefContext();

  // (window as any).ed = slateEditor;

  // const lastBlock = Editor.above(slateEditor, {
  //   match: n => Element.isElement(n) && Editor.isBlock(slateEditor, n),
  //   at: Editor.end(slateEditor, [0]),
  // });
  // console.log({lastBlock});

  useEffect(() => {
    const lastBlock = Editor.above(slateEditor, {
      match: n => Element.isElement(n) && Editor.isBlock(slateEditor, n),
      at: Editor.end(slateEditor, [0]),
    });

    if (lastBlock) {
      const [node, path] = lastBlock;
      const domNode = ReactEditor.toDOMNode(slateEditor, node);
      // Now you can work with domNode
      // TODO: working on this. re-enable all the calculations below.
      console.log(domNode);
    }
  }, [slateEditor]);

  // // TODO: this should probably live somewhere else. editor context?
  // const endNode =
  //   lastBlock == null
  //     ? 'hi'
  //     : ReactEditor.toDOMNode(
  //         slateEditor,
  //         lastBlock[0]
  //         // Editor.last(slateEditor, [0])[0]
  //       );

  const expressionEditorDomNode = expressionEditorDomRef.current;
  const runButtonDomNode = runButtonDomRef.current as unknown as HTMLDivElement; // TODO: fix type or drop semantic
  // if (weaveExpressionDomNode == null || runButtonDomNode == null) {
  //   return {
  //     maxLeft: 0,
  //     naturalLeft: 0,
  //     grandOffset: 0,
  //   };
  // }
  // console.log({endNode});
  return {maxLeft: 0, naturalLeft: 0, grandOffset: 0};

  // // TODO: review this logic. we should have a reusable hook for getting dimensions+offsets
  // let grandOffset = 0; // better name. what dimension??
  // for (let n = endNode; !n?.dataset.slateEditor; n = n?.parentNode as any) {
  //   if (n?.dataset.slateNode === 'element') {
  //     grandOffset += n!.offsetHeight;
  //   }
  //   grandOffset += n!.offsetTop;
  // }
  //
  // // TODO: rename
  // const maxLeft =
  //   expressionEditorDomNode == null || runButtonDomNode == null
  //     ? 0
  //     : expressionEditorDomNode.offsetWidth - runButtonDomNode.offsetWidth - 5;
  //
  // // TODO: rename
  // const naturalLeft = endNode.offsetLeft + endNode.offsetWidth + 10;
  //
  // return useMemo(
  //   () => ({
  //     // weaveExpressionDomRef,
  //     // runButtonDomRef,
  //     maxLeft,
  //     naturalLeft,
  //     grandOffset,
  //   }),
  //   [grandOffset, maxLeft, naturalLeft]
  // );

  // // Using setProperty because we need the !important priority on these
  // // since semantic-ui also sets it.
  // if (naturalLeft > maxLeft) {
  //   runButtonDomRef.style.setProperty('opacity', '0.3', 'important');
  // } else {
  //   runButtonDomRef.style.setProperty('opacity', '1.0', 'important');
  // }
  //
  // buttonNode.style.left = `${Math.min(maxLeft, naturalLeft)}px`;
  // buttonNode.style.top = `${grandOffset - 20}px`;
};
