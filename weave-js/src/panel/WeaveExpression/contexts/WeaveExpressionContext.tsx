export {};
// import {
//   createContext,
//   FC,
//   MutableRefObject,
//   PropsWithChildren,
//   useContext,
//   useMemo,
//   useRef,
// } from 'react';
// import {useToggle} from '@wandb/weave/hookUtils';
// import {WeaveExpressionProps} from '@wandb/weave/panel/WeaveExpression/WeaveExpression';
//
// import {SuggestionsProps} from '@wandb/weave/panel/WeaveExpression/contexts/ExpressionSuggestionsProvider';
//
// // TODO: this is obsolete.
// interface WeaveExpressionContextState {
//   // slateEditor: Editor;
//   weaveExpressionDomRef: MutableRefObject<HTMLDivElement | null>;
//   // slateProps: EditableProps; // TODO: no 'any'. ReturnType<typeof useWeaveDecorate>;
//   suggestions: SuggestionsProps;
//   // isFocused: boolean;
//   isDocsPanelVisible: boolean;
//   // isLiveUpdateEnabled: boolean;
//   toggleIsDocsPanelVisible: (newVal?: boolean) => void;
// }
//
// const WeaveExpressionContext = createContext<
//   WeaveExpressionContextState | undefined
// >(undefined);
// WeaveExpressionContext.displayName = 'WeaveExpressionContext';
//
// export const WeaveExpressionContextProvider: FC<
//   PropsWithChildren<WeaveExpressionProps>
// > = ({children, ...props}) => {
//   const weaveExpressionDomRef = useRef<HTMLDivElement | null>(null);
//
//   // TODO: rename the actual prop to 'expression'
//   const {expression, setExpression, isLiveUpdateEnabled = false} = props;
//
//   // TODO: problem useWeaveExpressionState needs a slateEditor. useSlateEditor needs useWeaveExpressionState. Circular dependency.
//
//   // Props used to initialize the expression state
//   // const weaveExpressionState = useWeaveExpressionState({props, slateEditor});
//   // const {applyPendingExpr, onChange, isValid, isTruncated} =
//   //   weaveExpressionState;
//
//   const {suggestions} = useExpressionSuggestions({
//     // slateStaticEditor,
//     expression,
//     setExpression,
//     isLiveUpdateEnabled,
//   });
//
//   const [isDocsPanelVisible, toggleIsDocsPanelVisible] = useToggle(false);
//
//   const contextState: WeaveExpressionContextState = useMemo(
//     () => ({
//       // slateEditor,
//       // slateComponentProps,
//       // editableComponentProps,
//       weaveExpressionDomRef,
//       // isFocused, // TODO: do we need this in context?
//       suggestions,
//       isDocsPanelVisible,
//       // isLiveUpdateEnabled,
//       toggleIsDocsPanelVisible,
//     }),
//     [isDocsPanelVisible, suggestions, toggleIsDocsPanelVisible]
//   );
//
//   return (
//     <WeaveExpressionContext.Provider value={contextState}>
//       {children}
//     </WeaveExpressionContext.Provider>
//   );
// };
//
// export function useWeaveExpressionContext() {
//   const context = useContext(WeaveExpressionContext);
//   if (context == null) {
//     throw new Error(
//       `useWeaveExpressionContext called outside of WeaveExpressionContext.Provider`
//     );
//   }
//   return context;
// }
