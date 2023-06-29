// const {isParsing, parseOutput, tsRoot} = useParsedText({editorText});
// TODO: rename this. takes text, returns expression result.
import {useWeaveContext} from '@wandb/weave/context';
import {usePanelContext} from '@wandb/weave/components/Panel2/PanelContext';
import {useCallback, useEffect, useState} from 'react';
import {ExpressionResult, voidNode} from '@wandb/weave/core';
import {trace} from '@wandb/weave/panel/WeaveExpression/util';
import * as Sentry from '@sentry/react';
import {useExpressionEditorText} from '@wandb/weave/panel/WeaveExpression/contexts/ExpressionEditorProvider';

const DEFAULT_PARSED_TEXT: ExpressionResult = {
  expr: voidNode(),
};
export const useParsedText = () => {
  // TODO: maybe grab editortext from context instead of props?
  const weave = useWeaveContext();
  const {stack} = usePanelContext();
  const [isParsingText, setIsParsingText] = useState(false);
  // TODO: rename parsedExpression
  const [parseResult, setParseResult] =
    useState<ExpressionResult>(DEFAULT_PARSED_TEXT);
  // // TODO: is undefined the right initial value for tsRoot?
  // // TODO: is this the right place for tsRoot? and why is it called tsRoot??
  // const [tsRoot, setTsRoot] = useState<SyntaxNode | undefined>(undefined);

  const editorText = useExpressionEditorText();

  // TODO: don't pass weave into here, i think.
  const parseText = useCallback(
    async (text: string) => {
      setIsParsingText(true);
      try {
        const output = await weave.expression(text, stack);
        //             if (this.parsePromise !== p) {
        //               this.trace(`parse result is stale, ignoring`);
        //               return;
        //             } else {
        //               this.parsePromise = null;
        //             }
        trace(`got parse result`, output);
        setParseResult(output); // TODO: do we need a deep equal check here? probably
        // this.parseState = parseResult;
        // setTsRoot(output.parseTree); // why do we save this in a separate state?
        // this.set('tsRoot', parseResult.parseTree);
        // clearSuggestions();
        // TODO: is this needed?
        // this.postUpdate('parse complete');
        // processParseState();
      } catch (err) {
        // TODO: probably want to generalize error handling? and factor out sentry.
        Sentry.captureException(err);
        // trace(`parseText error`, err);
        // this.parsePromise = null;
        // processParseState();
        // TODO: is this needed?
        // this.postUpdate('parse complete');
      } finally {
        setIsParsingText(false);
      }
    },
    // TODO: these probably change a lot.
    [stack, weave]
  );

  // TODO: should effect be here, and just export the result, or should we export parseText()?
  useEffect(() => {
    if (editorText.length === 0) {
      trace(`text is empty`);
      // Empty text, no need to parse
      // clearSuggestions();
      // TODO: is postUpdate needed?
      // this.postUpdate('clear expression complete');
      // processParseState();
      // setIsParsingText(false);
      return;
    }
    parseText(editorText);
    // return // TODO: cancel parse promise?
  }, [editorText, parseText]);

  // useEffect(() => {
  //   if (editorText == null) {
  //     return;
  //   }
  //   setIsParsing(true);
  //   const parseOutput = weave.parse(editorText);
  //   setParseOutput(parseOutput);
  //   setIsParsing(false);
  //   setTsRoot(parseOutput.tsRoot);
  // }, [editorText]);
  return {isParsingText, parseResult};
};
