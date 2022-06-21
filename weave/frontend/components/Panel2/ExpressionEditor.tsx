import * as S from './ExpressionEditor.styles';

import * as _ from 'lodash';
import * as React from 'react';
import {useEffect} from 'react';
import makeComp from '@wandb/common/util/profiler';
import * as CG from '@wandb/cg/browser/graph';
import * as HL from '@wandb/cg/browser/hl';
import * as Code from '@wandb/cg/browser/code';
import * as Types from '@wandb/cg/browser/model/types';
import * as CGTypes from '@wandb/cg/browser/types';
import * as EEState from './expEditorState';
import * as Panel2 from './panel';
import {ComputeGraphViz} from './ComputeGraphViz';
import {ExpressionView} from './ExpressionView';

import InlineStringEditor from './editors/InlineStringEditor';
import InlineNumberEditor from './editors/InlineNumberEditor';
import {Icon, Popup} from 'semantic-ui-react';
import {constString, constNumber} from '@wandb/cg/browser/ops';
import {WBAnchoredPopup} from '@wandb/common/components/WBAnchoredPopup';

const ArgsEditor2: React.FC<{
  args: CGTypes.EditingOpInputs;
  disabled?: boolean;
}> = makeComp(
  ({args, disabled}) => {
    const argNames = Object.keys(args);
    const argValues = Object.values(args);
    return (
      <>
        (
        {argValues.map((inNode, i) => (
          <span key={i}>
            {/* TODO: use argname as placeholder for nodeeditor */}
            {<NodeEditor node={inNode} disabled={disabled} />}
            {i < argNames.length - 1 && (
              <span style={{pointerEvents: 'none'}}>,&nbsp;</span>
            )}
          </span>
        ))}
        )
      </>
    );
  },
  {id: 'ArgEditor2'}
);

const OpEditor: React.FC<{op: CGTypes.EditingOp; disabled?: boolean}> =
  makeComp(
    ({op, disabled}) => {
      const focusedNodeOrOp = EEState.useFocusedNodeOrOp();
      const tailNode = EEState.useTailNode();
      const argNames = Object.keys(op.inputs);
      const argValues = Object.values(op.inputs);

      const opDef = CG.getOpDef(op.name);

      const validInput = HL.opInputsAreValid(op.inputs, opDef);
      const showError =
        !argValues.find(n => n === focusedNodeOrOp) && !validInput;

      if (HL.isBinaryOp(op)) {
        const needsParens = HL.opNeedsParens(op, tailNode);

        return (
          <>
            {needsParens && '('}
            <NodeEditor node={argValues[0]} disabled={disabled} />{' '}
            <S.OpWrapper error={showError}>
              <OpSuggestionWrapper op={op} disabled={disabled} />
            </S.OpWrapper>{' '}
            <NodeEditor node={argValues[1]} disabled={disabled} />
            {needsParens && ')'}
          </>
        );
      }

      if (HL.isBracketsOp(op)) {
        return (
          <>
            <NodeEditor node={argValues[0]} disabled={disabled} />
            <S.OpWrapper error={showError}>
              [
              <NodeEditor node={argValues[1]} disabled={disabled} />]
            </S.OpWrapper>
          </>
        );
      }

      if (HL.isDotChainedOp(op)) {
        return (
          <>
            <NodeEditor node={argValues[0]} disabled={disabled} />
            <S.OpWrapper error={showError}>
              .
              <OpSuggestionWrapper op={op} disabled={disabled} />
              {argNames.length > 1 && (
                <ArgsEditor2
                  args={_.pickBy(op.inputs, (v, k) => k !== argNames[0])}
                  disabled={disabled}
                />
              )}
            </S.OpWrapper>
          </>
        );
      }
      // Render as function call
      return (
        <S.OpWrapper error={showError}>
          <OpSuggestionWrapper op={op} disabled={disabled} />
          <ArgsEditor2 args={op.inputs} disabled={disabled} />
        </S.OpWrapper>
      );
    },
    {id: 'OpEditor'}
  );

const OpSuggestionWrapper: React.FC<{
  op: CGTypes.EditingOp;
  disabled?: boolean;
}> = makeComp(
  ({op, disabled}) => {
    const focusNodeOrOp = EEState.useAction(EEState.focusNodeOrOp);
    const focusedNodeOrOp = EEState.useFocusedNodeOrOp();
    const getLogContext = EEState.useGetLogContext('OpSuggestionWrapper', op);
    const [wrapperElement, setWrapperElement] =
      React.useState<HTMLElement | null>();

    const isHovered = EEState.useHoveredNodeOrOp() === op;
    const hoverNodeOrOp = EEState.useAction(EEState.hoverNodeOrOp);
    const unhoverNodeOrOp = EEState.useAction(EEState.unhoverNodeOrOp);

    return (
      <>
        <span
          data-test="op-suggestion-wrapper"
          data-op-name={op.name}
          ref={setWrapperElement}
          onClick={() => focusNodeOrOp(getLogContext('element clicked'), op)}
          onMouseEnter={() =>
            hoverNodeOrOp(getLogContext('element hovered'), op)
          }
          onMouseLeave={() =>
            unhoverNodeOrOp(getLogContext('element unhovered'), op)
          }>
          <AutoSuggestor
            nodeOrOp={op}
            defaultValue={HL.opDisplayName(op)}
            getLogContext={getLogContext}
            disabled={disabled}
          />

          {/* hide the op's own autocomplete while we're suggesting replacements for it,
            because otherwise the borders of the autosuggest menu can trigger hovers on the op,
            which feels weird */}
          {focusedNodeOrOp !== op && isHovered && wrapperElement && (
            <WBAnchoredPopup
              anchorElement={wrapperElement}
              triangleSize={0}
              // this card sometimes displays over the autosuggest -- so if autosuggest is
              // open for any node or op, then move this thing up and out of the way
              direction={focusedNodeOrOp ? 'top right' : 'bottom right'}>
              <S.OpDocCard opName={op.name} />
            </WBAnchoredPopup>
          )}
        </span>
      </>
    );
  },
  {
    id: 'OpSuggestionWrapper',
  }
);

const OutputNodeEditor: React.FC<{
  node: CGTypes.EditingOutputNode;
  disabled?: boolean;
}> = makeComp(
  ({node, disabled}) => {
    const focusedNodeOrOp = EEState.useFocusedNodeOrOp();
    const getLogContext = EEState.useGetLogContext('OutputNodeEditor', node);
    return (
      <>
        <OpEditor op={node.fromOp} disabled={disabled} />
        {focusedNodeOrOp === node && (
          <AutoSuggestor
            nodeOrOp={node}
            getLogContext={getLogContext}
            disabled={disabled}
          />
        )}
      </>
    );
  },
  {id: 'OutputNodeEditor'}
);

const VarNodeEditor: React.FC<{
  node: Types.VarNode;
  disabled?: boolean;
}> = makeComp(
  ({node, disabled}) => {
    const focusedNodeOrOp = EEState.useFocusedNodeOrOp();
    const getLogContext = EEState.useGetLogContext('VarNodeEditor', node);

    return (
      <>
        <S.VarName>{node.varName}</S.VarName>
        {focusedNodeOrOp === node && (
          <AutoSuggestor
            nodeOrOp={node}
            getLogContext={getLogContext}
            disabled={disabled}
          />
        )}
      </>
    );
  },
  {id: 'VarNodeEditor'}
);

const VoidNodeEditor: React.FC<{
  node: Types.VoidNode;
  disabled?: boolean;
}> = makeComp(
  ({node, disabled}) => {
    const getLogContext = EEState.useGetLogContext('VoidNodeEditor', node);

    return (
      <AutoSuggestor
        nodeOrOp={node}
        getLogContext={getLogContext}
        disabled={disabled}
      />
    );
  },
  {
    id: 'VoidNodeEditor',
  }
);

const ConstStringNodeEditor: React.FC<{
  node: Types.ConstNode<'string'>;
  disabled?: boolean;
}> = makeComp(
  ({node, disabled}) => {
    const getLogContext = EEState.useGetLogContext(
      'ConstStringNodeEditor',
      node
    );
    return (
      <>
        "
        <AutoSuggestor
          nodeOrOp={node}
          defaultValue={node.val}
          allowSpaces
          getLogContext={getLogContext}
          disabled={disabled}
        />
        "
      </>
    );
  },
  {id: 'ConstStringNodeEditor'}
);

const ConstNumberNodeEditor: React.FC<{
  node: Types.ConstNode<'number'>;
  extraSuggestor?: JSX.Element;
  disabled?: boolean;
}> = makeComp(
  ({node, extraSuggestor, disabled}) => {
    const focusNodeOrOp = EEState.useAction(EEState.focusNodeOrOp);
    const blurNodeOrOp = EEState.useAction(EEState.blurNodeOrOp);
    const setBuffer = EEState.useAction(EEState.setBuffer);
    const updateNodeAndFocus = EEState.useAction(EEState.updateNodeAndFocus);
    const focusedNodeOrOp = EEState.useFocusedNodeOrOp();
    const cursorPos = EEState.useCursorPos();
    const getLogContext = EEState.useGetLogContext(
      'ConstNumberNodeEditor',
      node
    );
    const handleEditorKeys = EEState.useHandleEditorKeys(false, getLogContext);

    return (
      <span onClick={e => e.stopPropagation()}>
        <InlineNumberEditor
          value={node.val}
          onKeyDown={!disabled ? handleEditorKeys : undefined}
          onFocus={
            !disabled
              ? e =>
                  focusNodeOrOp(
                    getLogContext('element received focus'),
                    node,
                    undefined,
                    e.currentTarget.textContent || ''
                  )
              : undefined
          }
          onBlur={
            !disabled
              ? () => blurNodeOrOp(getLogContext('element blurred'), node)
              : undefined
          }
          autofocus={focusedNodeOrOp === node}
          defaultCursorPos={focusedNodeOrOp === node ? cursorPos : undefined}
          extraSuggestor={extraSuggestor}
          // TODO: Min and max are unused in InlineNumberEditor, remove them?
          min={0}
          max={0}
          setValue={val => {
            if (!disabled) {
              updateNodeAndFocus(getLogContext('value finalized'), {
                ...node,
                val,
              });
            }
          }}
          onBufferChange={!disabled ? setBuffer : undefined}
        />
      </span>
    );
  },
  {id: 'ConstNumberNodeEditor'}
);

const ConstFunctionNodeEditor: React.FC<{
  node: Types.ConstNode<{
    type: 'function';
    inputTypes: {[key: string]: Types.Type};
    outputType: Types.Type;
  }>;
  disabled?: boolean;
}> = makeComp(
  ({node, disabled}) => {
    // const updateConstFunctionNode = EEState.useAction(
    //   EEState.updateConstFunctionNode
    // );
    const graph = EEState.useTailNode();

    let frame = EEState.useFrame();

    const consumingOpResult = HL.findConsumingOp(node, graph);
    if (consumingOpResult == null) {
      throw new Error('Invalid: function editor for non-argument function');
    }
    const {outputNode: consumingOpOutputNode} = consumingOpResult;
    const consumingOp = consumingOpOutputNode.fromOp;
    const inputNode = Object.values(consumingOp.inputs)[0];

    frame = HL.getFunctionFrame(consumingOp.name, inputNode, frame);

    const fnNode = node.val as Types.ConstNode<Types.FunctionType>;
    const inputVarNames = Object.keys(node.type.inputTypes);

    return (
      <span>
        ({inputVarNames.join(', ')}){' => '}
        {HL.nodeIsExecutable(inputNode) && inputNode.nodeType !== 'void' ? (
          <EEState.FrameContext.Provider value={frame}>
            <NodeEditor node={fnNode} disabled={disabled} />
          </EEState.FrameContext.Provider>
        ) : (
          <ExpressionView node={fnNode} />
        )}
      </span>
    );
  },
  {id: 'ConstFunctionNodeEditor'}
);

const ConstPanelConfigEditor: React.FC<{
  node: Types.ConstNode;
  op: CGTypes.EditingOp;
}> = makeComp(
  () => {
    return <span>&middot;</span>;
  },
  {id: 'ConstPanelConfigEditor'}
);

const AutoSuggestor: React.FC<{
  nodeOrOp: CGTypes.EditingNode | CGTypes.EditingOp;
  getLogContext: (origin: string) => EEState.LogContext;
  defaultValue?: string;
  allowSpaces?: boolean;
  disabled?: boolean;
}> = makeComp(
  ({nodeOrOp, getLogContext, defaultValue, allowSpaces, disabled}) => {
    allowSpaces = !!allowSpaces;

    const focusNodeOrOp = EEState.useAction(EEState.focusNodeOrOp);
    const blurNodeOrOp = EEState.useAction(EEState.blurNodeOrOp);
    const buffer = EEState.useBuffer();
    const setBuffer = EEState.useAction(EEState.setBuffer);
    const suggestions = EEState.useSuggestions();
    const updateNodeAndFocus = EEState.useAction(EEState.updateNodeAndFocus);
    const focusedNodeOrOp = EEState.useFocusedNodeOrOp();
    const handleEditorKeys = EEState.useHandleEditorKeys(
      allowSpaces,
      getLogContext
    );

    const cursorPos = EEState.useCursorPos();
    const isPanelOp =
      HL.isEditingOp(nodeOrOp) &&
      CG.opDefIsGeneratedWeave(CG.getOpDef(nodeOrOp.name));

    const onBufferChange = React.useCallback(
      (val: string) => {
        setBuffer(val);

        // if this change completes a suggestion and leaves no other options, accept the completed suggestion
        const suggestionMatch = suggestions.find(
          sugg => sugg.suggestionString.trim() === val
        );

        const otherPossibleRemainingMatches = suggestions.filter(
          sugg =>
            sugg !== suggestionMatch && sugg.suggestionString.includes(val)
        );
        if (suggestionMatch != null) {
          if (otherPossibleRemainingMatches.length === 0) {
            updateNodeAndFocus(
              getLogContext(
                `finalizing value because buffer matched suggestion "${suggestionMatch.suggestionString}"`
              ),
              suggestionMatch.newNodeOrOp
            );
            return;
          }
        }

        // a more obscure situation -- we've disambiguated the completions by trying to move on
        // to the next argument.
        //
        // easier by example -- consider: 3 <_
        //
        // that is, the cursor is after the < sign. There are two possible completions here,
        // < and <= . But if the next key we type is a number -- say, 5 -- then clearly our
        // intent was to accept the completion and move on: 3 < 5.
        const prevMatch = suggestions.find(
          sugg => sugg.suggestionString.trim() === buffer
        );
        const prevSuggestedNode = prevMatch?.newNodeOrOp;
        if (
          prevSuggestedNode &&
          HL.isEditingNode(prevSuggestedNode) &&
          prevSuggestedNode.nodeType === 'output'
        ) {
          const secondArg = Object.values(
            (prevSuggestedNode as CGTypes.EditingOutputNode).fromOp.inputs
          )[1];

          if (
            secondArg &&
            (val.endsWith(`'`) || val.endsWith(`"`)) &&
            HL.couldBeReplacedByType(secondArg, prevSuggestedNode, 'string')
          ) {
            updateNodeAndFocus(
              getLogContext(
                `Finalizing op ${
                  (prevSuggestedNode as CGTypes.EditingOutputNode).fromOp.name
                } because we tried to start a string literal after it`
              ),
              HL.replaceNode(prevSuggestedNode, secondArg, constString(''))
            );
            return;
          }

          const numberMatch = val.match(/(\d+)$/);

          if (secondArg && numberMatch) {
            const newKeyAsNumber = Number.parseFloat(numberMatch[1]);
            if (
              !Number.isNaN(newKeyAsNumber) &&
              HL.couldBeReplacedByType(secondArg, prevSuggestedNode, 'number')
            ) {
              const newKeyAsConstNode = constNumber(newKeyAsNumber);
              updateNodeAndFocus(
                getLogContext(
                  `Finalizing op ${
                    (prevSuggestedNode as CGTypes.EditingOutputNode).fromOp.name
                  } because we tried to start a number literal after it`
                ),
                HL.replaceNode(prevSuggestedNode, secondArg, newKeyAsConstNode),
                {
                  nodeOrOpToFocus: newKeyAsConstNode,
                  initialCursorAtEnd: true,
                }
              );
              return;
            }
          }
        }
      },
      [getLogContext, setBuffer, suggestions, updateNodeAndFocus, buffer]
    );

    const autocompleteOptions = React.useMemo(
      () =>
        !disabled
          ? suggestions.map((sugg, i) => ({
              name: sugg.suggestionString,
              value: i,
            }))
          : [],
      [disabled, suggestions]
    );

    const hovered = EEState.useHoveredNodeOrOp();
    const hoverNodeOrOp = EEState.useAction(EEState.hoverNodeOrOp);

    // as the user types, we should always select the first option of the filtered
    // list, as long as there's something
    React.useEffect(() => {
      if (autocompleteOptions.length > 0) {
        hoverNodeOrOp(
          getLogContext('highlighted autosuggest option'),
          suggestions[0]?.newNodeOrOp
        );
      }
    }, [autocompleteOptions.length, getLogContext, hoverNodeOrOp, suggestions]);

    // the lower-level components need the highlight in terms of the `value` in the
    // options objects -- in this case, just the index
    const highlightedIndex = React.useMemo(() => {
      const found = suggestions.findIndex(
        suggestion => suggestion?.newNodeOrOp === hovered
      );
      return found >= 0 ? found : null;
    }, [suggestions, hovered]);
    const onChangeHighlightedIndex = (
      newHighlightedIndex: string | number | null
    ) => {
      if (
        newHighlightedIndex == null ||
        typeof newHighlightedIndex === 'string'
      ) {
        return;
      }

      hoverNodeOrOp(
        getLogContext('highlighted autosuggest option'),
        suggestions[newHighlightedIndex]?.newNodeOrOp
      );
    };

    const contextPanelOp = React.useMemo(() => {
      if (
        !hovered ||
        !suggestions.find(suggestion => suggestion.newNodeOrOp === hovered)
      ) {
        // display nothing if nothing is hovered *or* if we're hovering something that
        // isn't an autocomplete suggestion
        return null;
      }

      if (HL.isEditingOp(hovered)) {
        return hovered.name;
      }

      if (hovered.nodeType === 'output') {
        return hovered.fromOp.name;
      }

      return null;
    }, [hovered, suggestions]);

    return (
      <span onClick={e => e.stopPropagation()}>
        <InlineStringEditor
          noQuotes
          disabled={disabled || isPanelOp}
          dataTest="auto-suggestor"
          elementType={
            isPanelOp ? 'panelOp' : HL.isEditingOp(nodeOrOp) ? 'op' : 'node'
          }
          defaultCursorPos={cursorPos}
          onFocus={
            !disabled
              ? e =>
                  focusNodeOrOp(
                    getLogContext('element got focus'),
                    nodeOrOp,
                    undefined,
                    e.currentTarget.textContent || ''
                  )
              : undefined
          }
          onBlur={
            !disabled
              ? () => blurNodeOrOp(getLogContext('element blurred'), nodeOrOp)
              : undefined
          }
          autocompleteOptions={autocompleteOptions}
          autofocus={!disabled && focusedNodeOrOp === nodeOrOp}
          value={defaultValue ?? ''}
          onKeyDown={
            !disabled
              ? e => {
                  handleEditorKeys(e);
                }
              : undefined
          }
          highlighted={highlightedIndex}
          onChangeHighlighted={onChangeHighlightedIndex}
          contextContent={
            contextPanelOp && (
              <S.OpDocCard isAutocomplete opName={contextPanelOp} />
            )
          }
          setValue={
            !disabled
              ? val => {
                  if (_.isNumber(val)) {
                    const pickedSuggestion = suggestions[val as any];
                    if (pickedSuggestion != null) {
                      updateNodeAndFocus(
                        getLogContext('value finalized'),
                        pickedSuggestion.newNodeOrOp
                      );
                    } else {
                      console.log(suggestions, val);
                    }
                  } else {
                    // TODO:
                  }
                }
              : () => {}
          }
          onBufferChange={!disabled ? onBufferChange : undefined}
        />
      </span>
    );
  },
  {id: 'AutoSuggestor'}
);

const ConstNodeEditor: React.FC<{
  node: Types.ConstNode;
  disabled?: boolean;
}> = makeComp(
  // TODO: What to do if inputType is no longer valid for a step?
  ({node, disabled}) => {
    const consumingOp = EEState.useConsumingOp(node);
    const isPanelConfig =
      consumingOp != null &&
      Panel2.isPanelOpName(consumingOp.outputNode.fromOp.name) &&
      consumingOp.argName === 'config';
    return CG.constNodeIsType(node, 'string') ? (
      <ConstStringNodeEditor node={node} disabled={disabled} />
    ) : CG.constNodeIsType(node, 'number') ? (
      <ConstNumberNodeEditor node={node} disabled={disabled} />
    ) : CG.constNodeIsType(node, {
        type: 'function',
        inputTypes: {},
        outputType: 'any',
      }) ? (
      <ConstFunctionNodeEditor
        node={node as Types.ConstNode<Types.FunctionType>}
        disabled={disabled}
      />
    ) : CG.constNodeIsType(node, {type: 'list', objectType: 'string'}) ? (
      <span>[{(node.val as string[]).join(', ')}]</span>
    ) : CG.constNodeIsType(node, 'none') ? (
      <span>None</span>
    ) : isPanelConfig ? (
      <ConstPanelConfigEditor
        node={node}
        op={consumingOp?.outputNode.fromOp!}
      />
    ) : CG.constNodeIsType(node, {type: 'typedDict', propertyTypes: {}}) ? (
      // TODO: This just renders it. Doesn't make it editable!
      <span>{JSON.stringify({...(node.val as any), _type: undefined})}</span>
    ) : (
      <div>No editor for type: {JSON.stringify(node.type, undefined, 2)}</div>
    );
  },
  {id: 'ConstNodeEditor'}
);

// Note: using this will break DAGs. We'll need a normalized
// representation if we want to avoid that.
export const NodeEditor: React.FC<{
  node: CGTypes.EditingNode;
  disabled?: boolean;
}> = makeComp(
  // TODO: What to do if inputType is no longer valid for a step?
  ({node, disabled}) => {
    return (
      <S.ExpressionEditor>
        {node.nodeType === 'var' ? (
          <VarNodeEditor node={node} disabled={disabled} />
        ) : node.nodeType === 'output' ? (
          <OutputNodeEditor node={node} disabled={disabled} />
        ) : node.nodeType === 'const' ? (
          <ConstNodeEditor node={node} disabled={disabled} />
        ) : (
          <VoidNodeEditor node={node} disabled={disabled} />
        )}
      </S.ExpressionEditor>
    );
  },
  {id: 'NodeEditor'}
);

export const ExpressionDebug: React.FC<{}> = makeComp(
  // TODO: What to do if inputType is no longer valid for a step?
  () => {
    const node = EEState.useTailNode();
    const focus = EEState.useFocusedNodeOrOp();
    return (
      <ComputeGraphViz
        node={node}
        highlightNodeOrOp={focus}
        width={600}
        height={300}
      />
    );
  },
  {id: 'ExpressionDebug'}
);

export const ExpressionEditorContainer: React.FC<{
  focusOnMount?: boolean;
  onAccept?: () => void;
  debug?: boolean;
  inline?: boolean;
  noBox?: boolean;
  disabled?: boolean;
  disableFreeText?: boolean;
}> = makeComp(
  // TODO: What to do if inputType is no longer valid for a step?
  ({focusOnMount, debug, noBox, inline, disabled, disableFreeText}) => {
    // updating using ref to work around: https://github.com/facebook/react/issues/8514
    const plainTextRef = React.useRef<HTMLInputElement>();
    const toggleShowPlainText = EEState.useAction(EEState.toggleShowPlainText);
    const showPlainText = EEState.useShowPlainText();
    const isEditingPlainText = EEState.useIsEditingPlainText();
    const plainTextHasError = EEState.usePlainTextHasError();
    const setIsEditingPlainText = EEState.useAction(
      EEState.setIsEditingPlainText
    );
    const setPlainTextExpression = EEState.useAction(
      EEState.setPlainTextExpression
    );
    const node = EEState.useTailNode();
    const focusOnTail = EEState.useAction(EEState.focusOnTail);

    useEffect(() => {
      if (focusOnMount) {
        // Use a set timeout. If we're rendering inside a semantic popup,
        // we need to delay a little bit to ensure we're in our final position
        setTimeout(() => {
          focusOnTail();
        }, 1);
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
      if (plainTextRef.current && !isEditingPlainText) {
        const stringified = HL.toString(node, null);

        if (plainTextRef.current.value !== stringified) {
          plainTextRef.current.value = stringified;
        }
      }
    }, [isEditingPlainText, node]);

    const getPlainTextSelection = () => {
      // we need this workaround because window.getSelection() doesn't work on textareas
      // in Firefox: https://bugzilla.mozilla.org/show_bug.cgi?id=85686

      const field = plainTextRef.current;
      if (!field) {
        return null;
      }

      const start = field.selectionStart ?? 0;
      const end = field.selectionEnd ?? 0;
      const text = field.value.substring(start, end);
      return {start, end, length: end - start, text};
    };
    const ee = (
      <S.ExpressionEditorContainer
        data-test="expression-editor-container"
        onMouseDown={(e: React.MouseEvent<HTMLDivElement>) => {
          // If e.target === e.currentTarget that means the mouse down event
          // happened directly on this div, rather than on a child. This means
          // the user has started to click inside the ExpressionEditor, but outside
          // of any of the elements of the expression. The browser seems to automatically
          // call .focus() on the last child of this container, which causes a glitch
          // because we focus on it and render suggestions, before focusOnTail() gets
          // called below, which then focuses on a different element and renders
          // a new auto-suggest list.
          // e.preventDefault() here prevents the browser from trying to focus on a
          // child. We'll do that ourselves, thank you very much!
          if (e.target === e.currentTarget) {
            e.preventDefault();
          }
        }}
        style={{display: 'inline-block'}}
        onBeforeInputCapture={e => {
          // Required otherwise Slate suppresses this event and any child contenteditable never changes
          // in response to keystrokes.
          e.stopPropagation();
        }}>
        <NodeEditor node={node as any} disabled={disabled} />
        {debug && <ExpressionDebug />}
      </S.ExpressionEditorContainer>
    );

    const eePlainText = (
      <S.ExpressionEditorPlainTextContainer>
        <S.ExpressionEditorPlainTextInput
          error={plainTextHasError}
          ref={e => {
            if (e && e !== plainTextRef.current) {
              // set the initial value -- we can't use defaultValue for this
              // because of: https://github.com/facebook/react/issues/8514#issuecomment-564660360
              e.value = HL.toString(node, null);
              e.focus();
              plainTextRef.current = e;
            }
          }}
          onKeyDown={e => {
            // On enter, revert back to regular editing mode.  Do nothing if there's a syntax error.
            if (e.code === 'Enter' && !plainTextHasError) {
              e.preventDefault();
              e.stopPropagation();
              toggleShowPlainText();
              focusOnTail();
              return;
            }

            const selection = getPlainTextSelection();
            if (
              e.keyCode === 57 &&
              selection &&
              selection.length > 0 &&
              plainTextRef.current
            ) {
              e.preventDefault();
              const newText =
                plainTextRef.current.value.slice(0, selection.start) +
                `(${selection.text})` +
                plainTextRef.current.value.slice(selection.end);

              plainTextRef.current.value = newText;
              plainTextRef.current.setSelectionRange(
                selection.start + 1,
                selection.end + 1
              );
              setPlainTextExpression(newText);
              return;
            }
          }}
          onFocus={() => setIsEditingPlainText(true)}
          onBlur={() => setIsEditingPlainText(false)}
          onChange={e => setPlainTextExpression(e.currentTarget.value)}
        />
        {isEditingPlainText ? (
          <S.ExpressionEditorTypeDisplay>
            {Types.toString(node.type, true)}
          </S.ExpressionEditorTypeDisplay>
        ) : null}
      </S.ExpressionEditorPlainTextContainer>
    );
    if (inline) {
      return (
        <span
          onClick={e => {
            e.stopPropagation();
            focusOnTail();
          }}>
          {ee}
        </span>
      );
    }
    return (
      <>
        <S.ExpressionEditorWrapper
          noBox={noBox}
          onClick={e => {
            e.stopPropagation();
            focusOnTail();
          }}
          showPlainText={showPlainText}>
          {showPlainText ? eePlainText : ee}
          {!disableFreeText && (
            <>
              {/* <div style={{width: 16}} /> */}
              <S.ExpressionEditorContextMenu>
                <S.ExpressionEditorContextMenuItem>
                  <Popup
                    content="Show/Hide Plain Text View"
                    size="small"
                    offset={-10}
                    trigger={
                      <S.ExpressionEditorContextMenuButton
                        size="small"
                        onClick={e => {
                          e.stopPropagation();
                          toggleShowPlainText();
                        }}>
                        <Icon
                          className="raw-input-toggle"
                          name="i cursor"
                          size="small"
                          style={{
                            lineHeight: 'inherit',
                            padding: '1px',
                            color: showPlainText ? '#2e78c7' : 'gray',
                          }}
                        />
                      </S.ExpressionEditorContextMenuButton>
                    }
                  />
                </S.ExpressionEditorContextMenuItem>
              </S.ExpressionEditorContextMenu>
            </>
          )}
        </S.ExpressionEditorWrapper>
      </>
    );
  },
  {id: 'ExpressionEditorContainer'}
);

export const ExpressionEditor: React.FC<{
  focusOnMount?: boolean;
  frame?: Code.Frame;
  node: CGTypes.EditingNode;
  onAccept?: () => void;
  debug?: boolean;
  inline?: boolean;
  noBox?: boolean;
  disabled?: boolean;
  disableFreeText?: boolean;
  updateNode(newNode: CGTypes.EditingNode): void;
}> = makeComp(
  // TODO: What to do if inputType is no longer valid for a step?
  ({
    focusOnMount,
    frame,
    node,
    updateNode,
    onAccept,
    debug,
    noBox,
    inline,
    disabled,
    disableFreeText,
  }) => {
    return (
      <EEState.EEContextProvider
        node={node}
        frame={frame}
        debug={debug}
        updateNode={!disabled ? updateNode : () => {}}>
        <ExpressionEditorContainer
          focusOnMount={focusOnMount}
          onAccept={onAccept}
          debug={debug}
          noBox={noBox}
          inline={inline}
          disabled={disabled}
          disableFreeText={disableFreeText}
        />
      </EEState.EEContextProvider>
    );
  },
  {id: 'ExpressionEditor'}
);
