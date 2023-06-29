import {
  defaultLanguageBinding,
  ExpressionResult,
  isVoidNode,
  voidNode,
} from '@wandb/weave/core';
import {useWeaveContext} from '@wandb/weave/context';
import {usePanelContext} from '@wandb/weave/components/Panel2/PanelContext';
import {useCallback, useEffect, useState} from 'react';
import {
  adaptSuggestions,
  getSelectionIndex,
  nodesAtOffset,
  rangeForSyntaxNode,
  trace,
} from '@wandb/weave/panel/WeaveExpression/util';
import * as Sentry from '@sentry/react';
import {SuggestionsProps} from '@wandb/weave/panel/WeaveExpression/contexts/ExpressionSuggestionsProvider';
import {useExpressionEditorContext} from '@wandb/weave/panel/WeaveExpression/contexts/ExpressionEditorProvider';

const DEFAULT_SUGGESTIONS: SuggestionsProps = {
  node: voidNode(),
  items: [],
  typeStr: null,
  isBusy: false,
};
// adapted from processSuggestionTarget
export const useSuggestionsForParsedExpression = ({
  expressionResult,
}: {
  expressionResult: ExpressionResult;
}) => {
  const weave = useWeaveContext();
  const {stack} = usePanelContext();
  const {expr, extraText, parseTree, nodeMap} = expressionResult;
  const {slateEditor} = useExpressionEditorContext();

  // TODO: this is just to get it compiling, but why do we need target, separate from expr?
  const target = expr;
  // const {expr, extraText} = this.parseState;
  // const target = this.suggestionTarget ?? expr;

  const [isSuggesting, setIsSuggesting] = useState(false);
  const [suggestions, setSuggestions] =
    useState<SuggestionsProps>(DEFAULT_SUGGESTIONS);

  const resetSuggestions = useCallback(() => {
    // this.suggestionTarget = null; // TODO: what is this?
    setSuggestions(DEFAULT_SUGGESTIONS);
    // clearSelectedSuggestion();
  }, []);

  // TODO: revisit all this! especially the editor stuff.
  const updateSuggestions = useCallback(async () => {
    trace(`🥮 updateSuggestions`, target, extraText);
    if (parseTree == null || nodeMap == null) {
      trace(`...no parse tree, nothing to update`);
      return;
    }
    setIsSuggesting(true);

    try {
      // const rawIndex = getSelectionIndex(this.editor);
      const rawIndex = getSelectionIndex(slateEditor);
      const [tsNodeAtCursor, cgNodeAtCursor] = nodesAtOffset(
        rawIndex,
        parseTree,
        nodeMap
      );

      // this.editor.activeNodeRange = rangeForSyntaxNode(
      //     tsNodeAtCursor,
      //     this.editor
      // );
      slateEditor.activeNodeRange = rangeForSyntaxNode(
        tsNodeAtCursor,
        slateEditor
      );

      // TODO: clean up adaptSuggestions
      const newSuggestionItems = await adaptSuggestions(
        weave,
        target,
        expr,
        stack,
        extraText
      );
      trace(`got new suggestions`, target, newSuggestionItems);
      // TODO: check this. what's isBusy??
      setSuggestions({
        node: target,
        typeStr: isVoidNode(target)
          ? null
          : defaultLanguageBinding.printType(target?.type ?? expr.type),
        items: newSuggestionItems,
        extraText,
        isBusy: false,
      });
      // postUpdate(`suggestions updated and no longer busy`);
    } catch (err) {
      Sentry.captureException(err);
      // this.trace(`suggestions error`, err);
      // this.suggestionsPromise = null;
      // postUpdate('suggestions failed');

      // TODO: re-enable this
      // if (err instanceof Error) {
      //   this.trace(`Error getting suggestionTarget:`, err.message);
      //   this.editor.activeNodeRange = null;
      // } else {
      //   this.trace(`Caught unknown value getting suggestionTarget:`, err);
      // }
      // this.postUpdate('failed to get suggestion target');
    } finally {
      setIsSuggesting(false);
    }
    // TODO: weave and stack probably change a lot?
  }, [expr, extraText, nodeMap, parseTree, slateEditor, stack, target, weave]);

  useEffect(() => {
    // TODO: fix promise ignored warning
    updateSuggestions();
  }, [updateSuggestions]);

  return {
    suggestions,
    isSuggesting,
    resetSuggestions,
  };
};
