import * as Sentry from '@sentry/react';
import {
  defaultLanguageBinding,
  EditingNode,
  ExpressionResult,
  isVoidNode,
  NodeOrVoidNode,
  Stack,
  voidNode,
  WeaveInterface,
} from '@wandb/weave/core';
import {Editor, Node as SlateNode} from 'slate';
import {ReactEditor} from 'slate-react';
import {SyntaxNode} from 'web-tree-sitter';

import type {
  SuggestionProps,
  WeaveExpressionAction,
  WeaveExpressionProps,
} from './types';
import {
  adaptSuggestions,
  getSelectionIndex,
  nodesAtOffset,
  rangeForSyntaxNode,
  trace,
} from './util';

let instanceCounter = 0;

export class WeaveExpressionState {
  public readonly id: string;
  public readonly isBusy: boolean;
  public readonly isValid: boolean;
  public readonly exprIsModified: boolean;
  public readonly editorValue: SlateNode[];
  public readonly suggestions: SuggestionProps;
  public readonly tsRoot: SyntaxNode | undefined;
  public readonly initializing: boolean;

  private setExpression: (expr: NodeOrVoidNode) => void;
  private hasPendingChanges: boolean;
  private parseState: ExpressionResult;
  private editorText: string;
  private parsePromise: Promise<void> | null;
  private suggestionsPromise: Promise<void> | null;
  private suggestionTarget: EditingNode | null;
  private pendingExpr: EditingNode;
  private trace: typeof trace;

  public constructor(
    private readonly props: Pick<
      WeaveExpressionProps,
      'setExpression' | 'liveUpdate' | 'expr'
    >,
    private readonly weave: WeaveInterface,
    private stack: Stack,
    private readonly editor: Editor,
    private readonly stateUpdated: (state: WeaveExpressionState) => void,
    private readonly replaceEditorText: (text: string) => void
  ) {
    this.id = `weave-expression-state-${instanceCounter++}`;
    this.trace = (...args: any[]) => trace(`${this.id}:`, ...args);

    this.trace('🤖 constructor', props);

    const exprText = weave.expToString(props.expr ?? voidNode(), null);

    // TODO(np): Fix this type to avoid cast.  We should always get a setExpression
    this.setExpression = props.setExpression as any;
    this.hasPendingChanges = false;
    this.parseState = {expr: voidNode()};
    this.editorText = exprText;
    this.parsePromise = null;
    this.suggestionsPromise = null;
    this.suggestionTarget = null;
    this.pendingExpr = props.expr ?? voidNode();

    this.isBusy = false;
    this.isValid = true;
    this.exprIsModified = false;
    this.editorValue = [
      {
        type: 'paragraph', // https://github.com/ianstormtaylor/slate/issues/3421
        children: [{text: this.editorText}],
      },
    ];
    this.suggestions = {
      node: voidNode(),
      typeStr: null,
      items: [],
      isBusy: false,
    };
    if (props.expr != null) {
      this.initializing = true;
      setTimeout(() => this.initialize(), 0);
    } else {
      this.initializing = false;
    }
  }

  public dispatch(action: WeaveExpressionAction) {
    switch (action.type) {
      case 'stackChanged':
        this.handleStackChanged(action.stack);
        return;
      case 'editorChanged':
        this.handleEditorChanged(action.newValue, action.stack);
        return;
      case 'exprChanged':
        this.handleExprChanged(action.expr);
        return;
      case 'setExprChanged':
        this.handleSetExprChanged(action.setExpr);
        return;
      case 'flushPendingExpr':
        this.handleFlushPendingExpr();
        return;
      default:
        this.trace(`dispatch(${(action as any).type}): Unknown action type`);
    }
  }

  private initialize() {
    this.replaceEditorText(this.editorText);
  }

  private clearSuggestions() {
    this.suggestionTarget = null;
    this.set('suggestions', {
      node: voidNode(),
      typeStr: null,
      items: [],
      isBusy: false,
    });
  }

  private handleStackChanged(newStack: Stack) {
    this.trace(`⛱️ handleStackChanged()`, newStack);
    this.processText(this.editorText, newStack);
  }

  private handleEditorChanged(newValue: SlateNode[], newStack: Stack) {
    this.trace(
      `🌈 handleEditorChanged()`,
      newValue,
      this.parseState,
      this.editorText
    );

    this.set('editorValue', newValue);

    const newText = newValue.reduce(
      (textFragment: string, line: SlateNode) =>
        textFragment + SlateNode.string(line),
      ''
    );

    if (newText !== this.editorText) {
      this.trace(`...text changed: "${this.editorText}" --> "${newText}"`);

      this.editorText = newText;
      this.processText(newText, newStack);
    } else if (this.initializing) {
      this.trace(`...got expected editorChanged event during initialization`);
      this.processText(newText, newStack);
    } else {
      this.trace(`...text unchanged, triggering suggestion update only`);
      this.updateSuggestions();
    }
  }

  private handleExprChanged(newExpr: EditingNode) {
    this.trace(
      `🦀 handleExprChanged()`,
      newExpr,
      this.parseState,
      this.editorText
    );
    if (newExpr == null) {
      this.trace('...newExpr is null, ignoring');
      return;
    }

    const exprText = this.weave.expToString(newExpr, null);
    if (exprText === this.editorText) {
      this.trace('...exprText is unchanged, ignoring');
      return;
    }

    // Inserting text into editor should result in an editorChanged action
    this.replaceEditorText(exprText);
  }

  private handleSetExprChanged(setExpression: (expr: NodeOrVoidNode) => void) {
    this.trace(`handleSetExprChanged`);
    this.setExpression = setExpression;
  }

  private handleFlushPendingExpr() {
    if (this.setExpression != null) {
      this.trace('🐸 applyPendingExpr', this.pendingExpr);
      this.setExpression(this.pendingExpr as NodeOrVoidNode);
    }
    this.set('exprIsModified', false);
    this.postUpdate('flushed changes');
  }

  private processText(newText: string, stack: Stack) {
    this.trace(`💎 processText()`, newText, stack);

    this.stack = stack;
    const p = this.weave
      .expression(newText, stack)
      .then(parseResult => {
        if (this.parsePromise !== p) {
          this.trace(`parse result is stale, ignoring`);
          return;
        } else {
          this.parsePromise = null;
        }
        this.trace(`got parse result`, parseResult);
        this.parseState = parseResult;
        this.set('tsRoot', parseResult.parseTree);
        this.clearSuggestions();
        this.postUpdate('parse complete');
        this.processParseState();
      })
      .catch(err => {
        Sentry.captureException(err);
        this.trace(`parse error`, err);
        this.parsePromise = null;
        this.postUpdate('parse failed');
      });
    this.parsePromise = p;
  }

  private processParseState() {
    this.trace(`🐬 processParseState()`, this.parseState, this.editor);
    if (this.initializing) {
      this.trace(`...initializing, skip to update suggestions`);
      this.updateSuggestions();
    } else {
      this.trace(`...update expression then suggestions`);
      this.updateExpr();
      this.updateSuggestions();
    }
  }

  private processSuggestionTarget() {
    const {expr, extraText} = this.parseState;
    const target = this.suggestionTarget ?? expr;

    this.trace(`🥮 processNewSuggestionTarget`, target, extraText);

    // Provide suggestions for target
    const p = adaptSuggestions(this.weave, target, expr, this.stack, extraText)
      .then(newSuggestions => {
        if (this.suggestionsPromise !== p) {
          trace(`suggestions are stale, ignoring`);
          return;
        } else {
          this.suggestionsPromise = null;
        }

        this.trace(`got new suggestions`, target, newSuggestions);
        this.set('suggestions', {
          node: target,
          typeStr: isVoidNode(target)
            ? null
            : defaultLanguageBinding.printType(target?.type ?? expr.type),
          items: newSuggestions,
          extraText,
          isBusy: false,
        });
        this.postUpdate(`suggestions updated and no longer busy`);
      })
      .catch(err => {
        Sentry.captureException(err);
        this.trace(`suggestions error`, err);
        this.suggestionsPromise = null;
        this.postUpdate('suggestions failed');
      });
    this.suggestionsPromise = p;
  }

  private updateExpr() {
    this.trace(
      `🐳 updateExpr()`,
      this.parseState.expr,
      this.parseState.extraText,
      `"${this.editorText}"`
    );

    if (this.parseState.extraText != null) {
      this.trace(`...have extra text, ignoring`);
      return;
    }

    const oldText = this.weave.expToString(
      this.pendingExpr ?? voidNode(),
      null
    );

    const newExpr = this.parseState.expr;
    const newText = this.weave.expToString(newExpr, null);

    if (newText === oldText) {
      this.trace(`...no change, ignoring "${this.editorText}" -> "${newText}"`);
      return;
    } else {
      this.trace(`...text changed: "${oldText}" -> "${newText}"`);
    }

    if (this.props.liveUpdate) {
      if (
        this.setExpression != null &&
        ((this.editorText.length !== 0 && newExpr.type !== 'invalid') ||
          this.editorText.length === 0)
      ) {
        this.trace(`...live updating expression`);
        this.setExpression(newExpr as NodeOrVoidNode);
      }
      return;
    }

    if (ReactEditor.isFocused(this.editor)) {
      this.trace(`...update pending expression`, newText);
      this.pendingExpr = newExpr;
      this.set('exprIsModified', true);
      this.postUpdate('expr is modified');
    } else {
      this.trace(`...not focused, done updating`);
    }
  }

  private updateSuggestions() {
    const {parseTree, nodeMap} = this.parseState;
    const rawIndex = getSelectionIndex(this.editor);

    // If the expression is syntactically correct, we should have a parse tree and
    // non-empty nodemap. Find the corresponding ts node for the cursor and update
    // our activeNodeRange and suggestionTarget
    if (parseTree && nodeMap && nodeMap.size > 0) {
      try {
        const [tsNodeAtCursor, cgNodeAtCursor] = nodesAtOffset(
          rawIndex,
          parseTree,
          nodeMap
        );

        this.editor.activeNodeRange = rangeForSyntaxNode(
          tsNodeAtCursor,
          this.editor
        );
        if (this.suggestionTarget !== cgNodeAtCursor) {
          this.trace(`setting suggestion target`, cgNodeAtCursor);
          this.suggestionTarget = cgNodeAtCursor ?? null;
          this.processSuggestionTarget();
        } else {
          this.trace(`suggestion target didn't change, nothing else to do.`);
          this.postUpdate('done recalculating suggestions');
        }
      } catch (err) {
        Sentry.captureException(err);
        if (err instanceof Error) {
          this.trace(`Error getting suggestionTarget:`, err.message);
          this.editor.activeNodeRange = null;
        } else {
          this.trace(`Caught unknown value getting suggestionTarget:`, err);
        }
        this.postUpdate('failed to get suggestion target');
      }
    } else {
      this.trace(`...no parse tree, nothing to update`);
    }
  }

  private set<T>(attr: keyof WeaveExpressionState, value: T) {
    this.trace(`set public attr ${attr} => ${value}`);
    (this as any)[attr] = value;
    this.hasPendingChanges = true;
    setTimeout(() => {
      if (this.hasPendingChanges) {
        this.trace('🤯 have changes that were never flushed!!!');
      }
    }, 1000);
  }

  private postUpdate(message: string) {
    this.set(
      'isValid',
      this.parseState.extraText == null &&
        (this.editor.children.length === 0 ||
          SlateNode.string(this.editor).trim().length === 0 ||
          !isVoidNode(this.parseState.expr as NodeOrVoidNode))
    );
    this.set(
      'isBusy',
      this.parsePromise != null || this.suggestionsPromise != null
    );

    if (this.isBusy) {
      this.trace('busy because:', this.parsePromise, this.suggestionsPromise);
    }

    this.hasPendingChanges = false;
    this.trace('posting update:', message);
    if (this.initializing) {
      this.trace('clear initializing flag on first update');
      this.set('initializing', false);
    }
    this.stateUpdated(this);
  }
}
