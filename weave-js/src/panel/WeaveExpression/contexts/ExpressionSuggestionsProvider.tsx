import {Editor, Location, Point, Range, Transforms} from 'slate';
import {FC, useCallback, useEffect, useMemo, useState} from 'react';
import {
  AutosuggestResult,
  EditingNode,
  NodeOrVoidNode,
} from '@wandb/weave/core';
import {
  moveToNextMissingArg,
  trace,
} from '@wandb/weave/panel/WeaveExpression/util.js';
import {ReactEditor} from 'slate-react';
import {useParsedText} from '@wandb/weave/panel/WeaveExpression/hooks/useParsedText';
import {useSuggestionsForParsedExpression} from '@wandb/weave/panel/WeaveExpression/hooks/useSuggestionsForParsedExpression';
import {
  AutosuggestResultAny,
  useSuggestionsDropdown,
} from '@wandb/weave/panel/WeaveExpression/hooks/useSuggestionsDropdown';
import {
  useSlateEditorContext,
  useSlateEditorText,
} from '@wandb/weave/panel/WeaveExpression/contexts/SlateEditorProvider';
import {
  GenericProvider,
  useGenericContext,
} from '@wandb/weave/panel/WeaveExpression/contexts/GenericProvider';
import {WeaveExpressionProps} from '@wandb/weave/panel/WeaveExpression/WeaveExpression';
import {usePropsContext} from '@wandb/weave/panel/WeaveExpression/contexts/PropsProvider';
import {useWeaveContext} from '@wandb/weave/context';

// TODO: figure out why this is necessary. what are the two different cases?
// revive it if necessary
// export function useExpressionSuggestionsWithSlateStaticEditor() {
//   const slateStaticEditor = useSlateStatic();
//   return useExpressionSuggestions({slateStaticEditor});
// }

// TODO: move this type
export interface SuggestionsProps {
  // For insert position hacks <- TODO: what hacks? look into this
  node: EditingNode; // can't this also be an OpNode or something? look at AutosuggestResult
  items: Array<AutosuggestResult<any>>; // TODO: this type is weird. are suggestions recursive?
  // TODO: maybe move some of these rando props into a SuggestionMetatada type
  typeStr: string | null; // the type of the node. null when node is void
  isBusy: boolean; // loading
  extraText?: string;
  forceHidden?: boolean;
  suggestionIndex?: number; // TODO: get rid of this
  // from types.ts:
}

export type ExpressionSuggestionsProviderInput = Pick<
  WeaveExpressionProps,
  'expression' | 'setExpression' | 'isLiveUpdateEnabled'
>;

interface ExpressionSuggestionsProviderOutput {
  // TODO: review these exports
  isValid: boolean;
  isDirty: boolean;
  isLoading: boolean;
  acceptSelectedSuggestion: () => void;
  clearSuggestions: () => void;
  suggestions: SuggestionsProps;
  parseResult: ReturnType<typeof useParsedText>['parseResult'];
  // clearSuggestions,
  hasSuggestions: boolean;
  // TODO: add an isLoading state here maybe?
}

export const ExpressionSuggestionsProvider: FC = ({children}) => {
  const expressionSuggestionsProviderOutput: ExpressionSuggestionsProviderOutput =
    useExpressionSuggestions();
  return (
    <GenericProvider<ExpressionSuggestionsProviderOutput>
      displayName="ExpressionSuggestionsContext"
      value={expressionSuggestionsProviderOutput}>
      {children}
    </GenericProvider>
  );
};

export const useExpressionSuggestionsContext = () =>
  useGenericContext<ExpressionSuggestionsProviderOutput>({
    displayName: 'ExpressionSuggestionsContext',
  });

const useExpressionSuggestions = (options?: {
  slateStaticEditor?: Editor; // TODO: get rid of this if we don't end up needing it
}): ExpressionSuggestionsProviderOutput => {
  const {
    expressionSuggestionsProviderInput: {
      expression,
      setExpression,
      isLiveUpdateEnabled = false,
    } = {}, // TODO: this seems like the wrong place to set this default
  } = usePropsContext();

  // necessary props?
  // - props.expr
  // - props.setExpression
  // - props.slateStaticEditor - maybe?
  // - props.isLiveUpdateEnabled

  const {slateEditor} = useSlateEditorContext();
  // If we are passed a slateStaticEditor, use that, otherwise use the one from context
  // TODO: figure out why this is necessary. what are the two different cases?
  const editor = options?.slateStaticEditor || slateEditor;

  // const [isLoading, setIsLoading] = useState(false);
  const [isValid, setIsValid] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  const convertExpressionToString = useConvertExpressionToString();
  const editorText = useSlateEditorText();
  console.log({editorText, expression});

  // TODO: we have the expression from the props, but also from parseResult. reconcile them.
  // ah i think maybe the parseResult should be a pending expression. when it's accepted, the props.expression changes
  const {isParsingText, parseResult} = useParsedText({editorText});

  // TODO: better naming
  const {expr: pendingExpression, extraText: pendingExpressionExtraText} =
    parseResult;
  const {type: pendingExpressionType} = pendingExpression;

  // validate the parsed expression
  useEffect(() => {
    const expressionIsValid =
      editorText.length > 0 && // TODO: we might not need this check... shouldn't pendingExpressionType be invalid if the text is empty?
      pendingExpressionType !== 'invalid' &&
      pendingExpressionExtraText == null;
    // TODO: compare to old validation below -- editor children?
    // this.set(
    //     'isValid',
    //     this.parseState.extraText == null &&
    //     // is empty?
    //     (this.editor.children.length === 0 ||
    //         SlateNode.string(this.editor).trim().length === 0 ||
    //         !isVoidNode(this.parseState.expr as NodeOrVoidNode))
    // );
    setIsValid(expressionIsValid);
  }, [editorText, pendingExpressionExtraText, pendingExpressionType]);

  // TODO: rename this
  const updateExpression = useCallback(
    (newExpression: EditingNode) => {
      // this.trace(`🐳 updateExpr()`, this.parseState.expr, this.parseState.extraText, `"${this.editorText}"`);

      if (!isValid || !isDirty || setExpression == null) {
        return;
      }

      // TODO: may have to compare with prevEditingText or prevExpression before setting but we'll see.
      // TODO: does this need a try/catch?
      setExpression(newExpression as NodeOrVoidNode); // TODO: what's up with the type cast??  //parsedExpression.expr as NodeOrVoidNode);
      setIsDirty(false);

      // // TODO: this was moved to the isDirty effect, but we lost the isFocused check... is that necessary?
      // // if the editor is focused, we want to update the pending expression
      // if (ReactEditor.isFocused(this.editor)) {
      //   this.trace(`...update pending expression`, newText);
      //   this.pendingExpr = newExpression;
      //   this.set('isDirty', true);
      //   this.postUpdate('expr is modified');
      // } else {
      //   this.trace(`...not focused, done updating`);
      // }
    },
    [isDirty, isValid, setExpression]
  );

  // If live update is enabled, update the expression immediately
  // If not, mark the expression as dirty
  useEffect(() => {
    // TODO: do we need to do a deep eq check here with the new expression?
    if (isLiveUpdateEnabled) {
      // trace(`...live updating expression`);
      updateExpression(pendingExpression);
      return;
    }
    // TODO: grep ReactEditor.isFocused(this.editor)  -- do we need to add it back in?
    setIsDirty(true);
    // this.postUpdate('expr is modified');
    // return updateExpression; // TODO: do we need a teardown function?
  }, [isLiveUpdateEnabled, pendingExpression, updateExpression]);

  // when you type...
  // - parse the text into an expression
  // - set that as the current expression, maybe? (pendingExpr?) and set isDirty and validate etc
  // - if currentExpression changes, and
  // - question: how come expression editor takes an expression as a prop? how do we reconcile that with currentExpr?

  // const {suggestions} = weaveExpressionState;
  // const [currentSuggestions, setCurrentSuggestions] =
  //   useState(DEFAULT_SUGGESTIONS);
  // const {node, extraText, isBusy} = currentSuggestions;

  const {suggestions, isSuggesting, resetSuggestions} =
    useSuggestionsForParsedExpression({
      expressionResult: parseResult,
    });
  const suggestionsNodeType = suggestions.node?.nodeType;

  const isLoading = isParsingText || isSuggesting;
  //
  // const suggestionItems = suggestions.items;
  // const {clearSelectedSuggestion, selectedSuggestion} = useSuggestionsDropdown({
  //   suggestionItems,
  // });

  // const clearSuggestions = useCallback(() => {
  //   // this.suggestionTarget = null; // TODO: what is this?
  //   setCurrentSuggestions(DEFAULT_SUGGESTIONS);
  // }, [clearSelectedSuggestion]);

  const {activeNodeRange} = editor;
  // Consolidated heuristics to deal with imperfect suggestions results
  // TODO: move to slate hook?
  const getInsertPoint = useCallback(() => {
    // const resultString = s.suggestionString.trim();
    // const resultString = expToString(s.newNodeOrOp, null);
    // By default, append the result to end of activeNodeRange if it exists, otherwise end of entire text
    let insertPoint: Range | Point = activeNodeRange ?? Editor.end(editor, []);

    // TODO: what does this mean. why are there two activeNodeRanges, both from editor?
    // oh, maybe it's about the type coercion?
    // TODO: do better
    if (suggestionsNodeType === 'var' || suggestionsNodeType === 'const') {
      // Suggestions for var nodes always include the var itself
      // Suggestions for const nodes always replace the const
      insertPoint = activeNodeRange as Range;
    }

    if (pendingExpressionExtraText == null) {
      return insertPoint;
      // return [resultString, resultAt];
    }

    // Point
    if (!Range.isRange(insertPoint)) {
      return {
        anchor: insertPoint,
        focus: {
          ...(insertPoint as Point),
          offset:
            (insertPoint as Point).offset +
            pendingExpressionExtraText.length +
            1,
        },
      }; // as Point, <- why doesn't this work
      //  as [string, Range | Point];
    }

    // Range
    const end = Range.end(insertPoint);
    return {
      anchor: Range.start(insertPoint),
      focus: {
        ...end,
        offset: end.offset + pendingExpressionExtraText.length,
      },
    };
  }, [
    activeNodeRange,
    editor,
    pendingExpressionExtraText,
    suggestionsNodeType,
  ]);

  // TODO: fix 'any'
  // TODO: some or all of this should get moved to editor hook
  const acceptSuggestion = useCallback(
    (sugg?: AutosuggestResultAny) => {
      trace('acceptSuggestion', sugg);
      if (sugg == null || isLoading) {
        return;
      }

      ReactEditor.focus(editor);
      const suggestionString = convertExpressionToString(
        sugg.newNodeOrOp,
        null
      );
      // const [suggestion, insertPoint] = applyHacks(sugg);
      const insertPoint = getInsertPoint();
      const prevSelection = {...editor.selection}; // TODO: should be a usePrevious hook?
      Transforms.insertText(editor, suggestionString, {
        at: insertPoint,
      });
      Transforms.select(editor, prevSelection as Location);
      moveToNextMissingArg(editor);
    },
    [isLoading, editor, convertExpressionToString, getInsertPoint]
  );

  const suggestionItems = suggestions.items;

  const {acceptSelectedSuggestion, clearSelectedSuggestion} =
    useSuggestionsDropdown({
      suggestionItems,
      acceptSuggestion,
    });

  const clearSuggestions = useCallback(() => {
    clearSelectedSuggestion();
    resetSuggestions();
  }, [clearSelectedSuggestion, resetSuggestions]);
  //   setCurrentSuggestions(DEFAULT_SUGGESTIONS);
  // const acceptSelectedSuggestion = useCallback(
  //   () => acceptSuggestion(selectedSuggestion),
  //   [acceptSuggestion, selectedSuggestion]
  // );

  const hasSuggestions = suggestionItems.length > 0;

  return useMemo(
    () => ({
      // TODO: review these exports
      isValid,
      isDirty,
      isLoading,
      acceptSelectedSuggestion,
      clearSuggestions,
      suggestions,
      // clearSuggestions,
      hasSuggestions,
      parseResult,
      // TODO: add an isLoading state here maybe?
    }),
    [
      acceptSelectedSuggestion,
      clearSuggestions,
      hasSuggestions,
      isDirty,
      isLoading,
      isValid,
      parseResult,
      suggestions,
    ]
  );
};

// TODO: is this dumb? move elsewhere?
export const useConvertExpressionToString = () => {
  const weave = useWeaveContext();
  return weave.expToString;
};
