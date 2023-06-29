export {};
// import {Node as SlateNode} from 'slate';
// import {
//   isVoidNode,
//   NodeOrVoidNode,
//   Stack,
//   voidNode,
//   WeaveInterface,
// } from '@wandb/weave/core';
// import {usePanelContext} from '@wandb/weave/components/Panel2/PanelContext';
// import {useCallback, useEffect, useRef, useState} from 'react';
// import _ from 'lodash';
// import {trace} from '@wandb/weave/panel/WeaveExpression/util';
// import {WeaveExpressionProps} from '@wandb/weave/panel/WeaveExpression/WeaveExpression';
// import {useWeaveContext} from '@wandb/weave/context';
// import {useExpressionSuggestions} from './useExpressionSuggestions';
//
// // TODO: should this be moved to where the stack is created??
// function serializeStack(stack: Stack, weave: WeaveInterface) {
//   return _.map(stack, weave.expToString.bind(weave));
// }
//
// // TODO: reconcile this with useWeaveExpressionContext
// // TODO: we shouldn't have to pass in weave and editor here
// export const useWeaveExpressionState = ({
//   props,
// }: // slateEditor,
// {
//   props: WeaveExpressionProps;
//   // slateEditor: Editor;
//   // weave: WeaveInterface
// }) => {
//   // // Most of the state is managed by the WeaveExpressionState class.
//   // // This hook manages the state object and its lifecycle, and
//   // // avoids recreating the class when the props change in response
//   // // to a new expression being entered.
//   // const currentProps = useRef(props);
//
//   // const weave = useWeaveContext();
//
//   const {
//     expr,
//     isTruncated,
//     isLiveUpdateEnabled,
//     setExpression,
//     noBox,
//     // slate editor stuff
//     onFocus,
//     onBlur,
//     onMount,
//   } = props;
//
//   const {stack} = usePanelContext();
//   const weave = useWeaveContext();
//   const currentStack = useRef(stack).current; // TODO: is this ref necessary?
//
//   // const [isLoading, setIsLoading] = useState(false);
//   // const [isValid, setIsValid] = useState(false);
//
//   // const [isDirty, setIsDirty] = useState(false);
//
//   // move to slate context?
//   const editorText = weave.expToString(props.expr ?? voidNode(), null);
//   const [slateValue, setSlateValue] = useState<SlateNode[]>([
//     {
//       type: 'paragraph', // https://github.com/ianstormtaylor/slate/issues/3421
//       children: [{text: editorText}],
//     },
//   ]);
//
//   const {clearSuggestions} = useExpressionSuggestions();
//   // const hasPendingChanges = useRef(false);
//   // const {isParsing, parsedText, tsRoot} = useParsedText({editorText});
//
//   useEffect(() => {
//     clearSuggestions();
//     postUpdate('clear expression complete');
//     processParseState();
//   }, [parsedText]);
//
//   const isLoading = isParsing || isSuggesting;
//
//   // const [parseState, setParseState] =
//   //   useState<ExpressionResult>(DEFAULT_PARSE_STATE);
//   const postUpdate = useCallback((message: string) => {
//     // this.set(
//     //   'isValid',
//     //   this.parseState.extraText == null &&
//     //     // is empty?
//     //     (this.editor.children.length === 0 ||
//     //       SlateNode.string(this.editor).trim().length === 0 ||
//     //       !isVoidNode(this.parseState.expr as NodeOrVoidNode))
//     // );
//     setIsValid(
//       parseOutput.extraText == null &&
//         // TODO: make an editor is empty hook
//         (this.editor.children.length === 0 ||
//           SlateNode.string(this.editor).trim().length === 0 ||
//           !isVoidNode(parseOutput.expr as NodeOrVoidNode))
//     );
//     // this.set(
//     //   'isBusy',
//     //   setIsLoading()
//     setIsLoading(isParsing || this.suggestionsPromise != null);
//     // );
//
//     if (isLoading) {
//       trace('isLoading:', {isParsing, isSuggesting});
//     }
//
//     // this.hasPendingChanges = false;
//     // this.trace('posting update:', message);
//     // if (this.initializing) {
//     //   this.trace('clear initializing flag on first update');
//     //   this.set('initializing', false);
//     // }
//     // this.stateUpdated(this
//   }, []);
//   return {};
// };
