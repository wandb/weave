import {
  allVarsWillResolve,
  callOpVeryUnsafe,
  ConstNode,
  constNodeUnsafe,
  dereferenceAllVars,
  EditingNode,
  filterNodes,
  findChainedAncestors,
  isAssignableTo,
  isListLike,
  isSimpleTypeShape,
  listObjectType,
  mapNodes,
  Node,
  NodeOrVoidNode,
  nullableTaggableValue,
  OutputNode,
  pushFrame,
  replaceNode,
  resolveVar,
  Type,
  varNode,
  voidNode,
} from '@wandb/weave/core';
import _ from 'lodash';
import {
  Dispatch,
  SetStateAction,
  SyntheticEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {DropdownProps} from 'semantic-ui-react';

import {useWeaveFeaturesContext} from '../../../context';
import {useWeaveContext} from '../../../context';
import {usePrevious} from '../../../hookUtils';
import {useExpandedNode} from '../../../react';
import {PanelStack, usePanelStacksForType} from '../availablePanels';
import {useChildUpdateConfig2} from '../libchildpanel';
import {
  isPanelOpName,
  PanelConvertSpec,
  panelIdToPanelOpName,
  panelOpNameToPanelId,
} from '../panel';
import {usePanelContext} from '../PanelContext';
import {
  makeEventRecorder,
  trackWeavePanelEvent,
} from '../panellib/libanalytics';
import {useRefineExpressionEffect} from '../panellib/libexp';
import {getStackIdAndName} from '../panellib/libpanel';
import {ConverterSpecs} from '../PanelRegistry';
import {Spec as PanelTableMergeSpec} from '../PanelTableMerge';
import {
  EMPTY_EXPRESSION_PANEL,
  PanelExpressionConfig,
  PanelExpressionProps,
} from './common';

const recordEvent = makeEventRecorder('Expression');

const PANEL_OPTION_PREFIX = {
  eject: '<Eject>',
};

// Helper function to generate an "english"-friendly name
// to use in the expression.
const useVarNameFromType = (t: Type): string => {
  return useMemo(() => {
    let varName: string = 'x';
    let inputSimpleType = nullableTaggableValue(t);
    // Note: This won't always be correct. Generalize!
    let plural = false;
    if (isListLike(inputSimpleType)) {
      inputSimpleType = nullableTaggableValue(listObjectType(inputSimpleType));
      plural = true;
    }
    if (isSimpleTypeShape(inputSimpleType)) {
      varName = inputSimpleType;
      if (plural) {
        varName += 's';
      }
    }
    return varName;
  }, [t]);
};

function isUpdateDeletionOfTailPanelOp(
  cExp: EditingNode | undefined,
  nExp: EditingNode | undefined
) {
  return (
    nExp != null &&
    cExp?.nodeType === 'output' &&
    cExp.fromOp.inputs.config?.nodeType === 'const' &&
    isPanelOpName(cExp.fromOp.name ?? '') &&
    // it would be nice to not have to do a refine here.
    _.isEqual(nExp, cExp.fromOp.inputs.input)
  );
}
function isTablePanelHandler(currHandler: PanelStack | undefined) {
  return (
    currHandler?.id === 'table' ||
    (currHandler?.id === 'merge' && (currHandler as any)?.child?.id === 'table')
  );
}

function useSynchronizedState<T>(obj: T): [T, Dispatch<SetStateAction<T>>] {
  const [copy, setCopy] = useState(obj);
  const lastObj = usePrevious(obj);
  useEffect(() => {
    if (lastObj !== obj) {
      setCopy(obj);
    }
  }, [lastObj, obj, setCopy]);

  return [copy, setCopy];
}

function makeSpine(node: EditingNode<Type>): null | string {
  if (node.nodeType === 'output') {
    const currentName = node.fromOp.name;
    const inputs = Object.values(node.fromOp.inputs);
    const parentSpine =
      inputs.length > 0
        ? makeSpine(Object.values(node.fromOp.inputs)[0])
        : null;
    if (parentSpine != null) {
      return `${parentSpine}.${currentName}`;
    } else {
      return currentName;
    }
  } else if (node.nodeType === 'var') {
    return `var-${node.varName}`;
  }

  return null;
}

export type PanelExpressionState = ReturnType<typeof usePanelExpressionState>;

export function usePanelExpressionState(props: PanelExpressionProps) {
  useEffect(() => {
    recordEvent('VIEW');
  }, []);

  const devPopup = useWeaveFeaturesContext().betaFeatures['weave-devpopup'];
  // Globally disabling this since:
  // a) it does not play nicely with EE
  // b) i have seen a bunch of internal folks (Lukas included) that have
  // this enabled!! This could result in nasty bugs if they are not careful.
  const weavePlotEnabled = false;
  const weave = useWeaveContext();
  const {updateConfig: unprotectedUpdateConfig} = props;
  const inputNode = props.input;

  const [configOpen, setConfigOpen] = useState(false);

  const [updatingConfig, setUpdatingConfig] = useState(false);
  const config = useMemo(
    () =>
      !_.isEmpty(props.config) ? props.config : {...EMPTY_EXPRESSION_PANEL},
    [props.config]
  );
  const updateConfig = useCallback<typeof unprotectedUpdateConfig>(
    update => {
      if (config.exprAndPanelLocked) {
        update = _.omit(update ?? {}, ['exp', 'panelId']);
      }
      unprotectedUpdateConfig(update);
    },
    [config, unprotectedUpdateConfig]
  );
  const {updateConfig2: parentUpdateConfig2} = props;
  const updateConfig2 = useChildUpdateConfig2(
    'panel-expression',
    parentUpdateConfig2 as any
  );
  // Use a nicer variable name if we can
  const varName = useVarNameFromType(inputNode.type);

  const panelContext = usePanelContext();
  const newVars = useMemo(() => {
    if (inputNode.nodeType === 'void') {
      return {};
    } else {
      return {[varName]: inputNode};
    }
  }, [inputNode, varName]);
  const stack = useMemo(() => {
    return pushFrame(panelContext.stack, newVars);
  }, [newVars, panelContext.stack]);

  // Some user workspaces have persisted expressions that assume
  // certain variables are in scope, and/or that this component
  // will fix them automatically.  Walk the expression and rename
  // any variables outside of any function literals and,
  // if they don't exist in the frame, rename them to the
  // "canonical" var name calculated from the type.
  const exp: NodeOrVoidNode<Type> = useMemo(() => {
    if (inputNode.nodeType === 'void') {
      return (config.exp as NodeOrVoidNode) ?? voidNode();
    }
    return config.exp
      ? (mapNodes(
          config.exp,
          node => {
            if (
              node.nodeType === 'var' &&
              resolveVar(stack, node.varName) == null &&
              (node.type !== inputNode.type || node.varName !== varName)
            ) {
              return varNode(inputNode.type, varName);
            }

            return node;
          },
          true
        ) as NodeOrVoidNode)
      : voidNode();
  }, [config.exp, inputNode.nodeType, inputNode.type, stack, varName]);

  // console.log('EXPRESSION FOR useRefineExpressionEffect', exp, 'FRAME', frame);
  const refinedExpressionLoader = useRefineExpressionEffect(
    exp as any,
    stack,
    weave
  );

  const {loading: isRefining} = refinedExpressionLoader;
  const refinedExpression = refinedExpressionLoader.loading
    ? exp
    : refinedExpressionLoader.result;

  const {loading: isExpanding, result: expanded} =
    useExpandedNode(refinedExpression);

  // Call the user's expression. If the expression contains variables that
  // are no longer present in the frame, then the result is void.
  const callNode = useCallback(
    (node: NodeOrVoidNode<Type>) => {
      const withCall =
        node.nodeType !== 'void' ? dereferenceAllVars(node, stack).node : node;
      if (!allVarsWillResolve(withCall, stack)) {
        return voidNode();
      }
      return withCall;
    },
    [stack]
  );

  const calledExpanded = useMemo(
    () => callNode(expanded),
    [callNode, expanded]
  );

  // Keep a separate copy of the config we're editing
  const [editingPanelConfigBase, setEditingPanelConfig] = useSynchronizedState(
    config.panelConfig
  );

  const deleteTailPanelOps = useCallback(
    async (extraConfigUpdate?: {[key: string]: any}) => {
      setUpdatingConfig(true);
      let currentExp = await weave.refineNode(exp as Node, stack);
      let currentPanelConfig = props.config?.panelConfig;
      let newExp =
        currentExp?.nodeType === 'output'
          ? currentExp.fromOp.inputs[Object.keys(currentExp.fromOp.inputs)[0]]
          : null;

      while (
        newExp != null &&
        isUpdateDeletionOfTailPanelOp(currentExp, newExp)
      ) {
        currentPanelConfig = {
          ...((currentExp as OutputNode).fromOp.inputs.config as ConstNode).val,
          // Note: this ...currentPanelConfig is sort of a hack to ensure
          // that prior panel states don't overwrite the current one.
          // This needs to be fixed with a large panel expression config
          // refactor. We should be storing configs per handler id, so we
          // don't mix them. In fact, this should be part of a broader "config"
          // class/utility that allows versioning and key validation for configs.
          ...currentPanelConfig,
          childConfig: {...currentPanelConfig},
        };
        currentExp = newExp;
        newExp = (currentExp as OutputNode).fromOp.inputs.input;
      }
      setEditingPanelConfig(currentPanelConfig);
      updateConfig({
        exp: currentExp,
        panelConfig: currentPanelConfig,
        ...(extraConfigUpdate ?? {}),
      });
      setUpdatingConfig(false);
    },
    [
      weave,
      exp,
      stack,
      props.config?.panelConfig,
      setEditingPanelConfig,
      updateConfig,
    ]
  );

  // TODO: this is not great, it blows away panelId and panelConfig!
  // Also it is called asynchronously after a refine by updatePanelInput, which means
  // its could have captured stale state in the closure. Should use updateConfig2 instead.
  const updateExp = useCallback(
    (newExp: EditingNode) => {
      updateConfig({exp: newExp, panelId: undefined, panelConfig: undefined});
      recordEvent('EXP_UPDATE');
    },
    [updateConfig]
  );

  const updatePanelId = useCallback(
    (newPanelId: string | undefined) => {
      updateConfig({panelId: newPanelId});
    },
    [updateConfig]
  );

  const updatePanelInput = useCallback<any>(
    (newInput: Node) => {
      if (refinedExpression.nodeType === 'void') {
        throw new Error(
          'PanelExpression.updatePanelInput: expected refinedExpression.nodeType not to be void, found ' +
            refinedExpression.nodeType
        );
      }
      let newExp: Node;
      if (
        filterNodes(
          newInput,
          checkNode =>
            checkNode.nodeType === 'var' && checkNode.varName === 'input'
        ).length === 0
      ) {
        newExp = newInput;
      } else {
        newExp = weave.callFunction(newInput, {
          input: refinedExpression,
        });
      }
      const doUpdate = async () => {
        try {
          const refined = await weave.refineNode(newExp, stack);
          updateExp(refined);
        } catch (e) {
          return Promise.reject(e);
        }
        return Promise.resolve();
      };
      doUpdate().catch(e => {
        console.error('PanelExpression error', e);
        throw new Error(e);
      });
    },
    [updateExp, refinedExpression, stack, weave]
  );

  const {handler, stackIds} = usePanelStacksForType(
    calledExpanded.type,
    config.panelId,
    {
      excludeMultiTable:
        refinedExpression.nodeType === 'output' &&
        refinedExpression.fromOp.name ===
          panelIdToPanelOpName(PanelTableMergeSpec.id),
      showDebug: devPopup,
    }
  );

  const curPanelName =
    handler != null ? getStackIdAndName(handler).displayName : '';

  const [editingExp, setEditingExp] = useSynchronizedState(refinedExpression);

  const calledRefined = useMemo(
    () => callNode(editingExp),
    [callNode, editingExp]
  );
  const inputPath = useMemo(
    () => calledExpanded as Node<Type>,
    [calledExpanded]
  );

  // We keep track of the last type that our panel was configured for.
  // If the current handler can't handle that type, then reset the config
  // to {}
  const renderPanelConfig = useMemo(
    () => config.panelConfig,
    // TODO: ok to remove this?
    // isAssignableTo(calledExpanded.type, config.panelInputType ?? 'void') ||
    // (handler != null &&
    //   isAssignableTo(calledExpanded.type, handler.inputType))
    //   ? config.panelConfig ?? null
    //   : null,
    [config.panelConfig]
  );
  const editingPanelConfig = useMemo(
    () =>
      isAssignableTo(calledExpanded.type, config.panelInputType ?? 'void') ||
      (handler != null &&
        isAssignableTo(calledExpanded.type, handler.inputType))
        ? editingPanelConfigBase ?? null
        : null,
    [
      config.panelInputType,
      editingPanelConfigBase,
      calledExpanded.type,
      handler,
    ]
  );

  const updateEditingPanelConfig = useCallback<any>(
    (newConfig: any) => {
      setEditingPanelConfig({...(editingPanelConfig ?? {}), ...newConfig});
    },
    [editingPanelConfig, setEditingPanelConfig]
  );
  const updateRenderPanelConfig = useCallback<any>(
    (newConfig: any) => {
      const panelConfig = {...(renderPanelConfig ?? {}), ...newConfig};
      updateConfig({
        panelInputType: calledExpanded.type,
        panelConfig,
      });
      // For now, we also update the editing config. This means when the
      // user interacts with the main panel, we update the underlying editing config
      // representation.
      updateEditingPanelConfig(panelConfig);
    },
    [
      updateConfig,
      renderPanelConfig,
      calledExpanded.type,
      updateEditingPanelConfig,
    ]
  );

  const updateEditingPanelConfig2 = useCallback<any>(
    (change: <T>(oldConfig: T) => Partial<T>) => {
      setEditingPanelConfig((currentConfig: PanelExpressionConfig) => {
        return change(currentConfig);
      });
    },
    [setEditingPanelConfig]
  );
  const updateRenderPanelConfig2 = useCallback<any>(
    // TODO: This calls updateEditingPanelConfig in the old implementation!
    //    this is important!
    (change: <T>(oldConfig: T) => Partial<T>) => {
      updateConfig2((currentConfig: PanelExpressionConfig) => {
        return {
          panelInputType: calledExpanded.type,
          panelConfig: change(currentConfig.panelConfig),
        };
      });
    },
    [calledExpanded.type, updateConfig2]
  );

  const applyEditingConfig = useCallback(() => {
    recordEvent('EDITING_CONFIG_UPDATE');
    updateConfig({
      exp: editingExp,
      panelInputType: calledExpanded.type,
      panelConfig: editingPanelConfig,
    });
  }, [calledExpanded.type, editingPanelConfig, updateConfig, editingExp]);

  const discardEditingConfig = useCallback(() => {
    setEditingPanelConfig(renderPanelConfig);
    setEditingExp(refinedExpression as any);
  }, [
    renderPanelConfig,
    refinedExpression,
    setEditingPanelConfig,
    setEditingExp,
  ]);

  const expArgsAreModified = useMemo(
    () => !_.isEqual(editingExp, refinedExpression),
    [editingExp, refinedExpression]
  );

  const editingConfigIsModified = useMemo(
    () =>
      !_.isEqual(renderPanelConfig, editingPanelConfig) || expArgsAreModified,
    [renderPanelConfig, editingPanelConfig, expArgsAreModified]
  );

  const updateEditingConfigurableNode = useCallback(
    async (currentNode: Node<any>, newNode: Node<any>) => {
      const replacedNode = replaceNode(editingExp, currentNode, newNode);
      setEditingExp(replacedNode as any);
    },
    [editingExp, setEditingExp]
  );
  const configurableNodeSettings = useMemo(() => {
    const configurableNodes =
      calledRefined.nodeType === 'void'
        ? []
        : (findChainedAncestors(calledRefined, node => {
            return (
              node.nodeType === 'output' && isPanelOpName(node.fromOp.name)
            );
          }) as Array<OutputNode<Type>>);
    return configurableNodes
      .reverse()
      .map(node => {
        const foundPanel = ConverterSpecs().find(
          spec => spec.id === panelOpNameToPanelId(node.fromOp.name)
        );
        if (foundPanel != null) {
          const keys = Object.keys(node.fromOp.inputs);
          const fromInputNode = node.fromOp.inputs[keys[0]];
          const configNode = node.fromOp.inputs.config;
          return {
            node: fromInputNode,
            panel: foundPanel,
            config: (configNode as ConstNode).val ?? {},
            updateEditingConfig: (newConfig: any) =>
              updateEditingConfigurableNode(
                configNode,
                constNodeUnsafe('any', newConfig)
              ),
          };
        }
        return null;
      })
      .filter(x => x != null) as Array<{
      node: OutputNode<Type>;
      panel: PanelConvertSpec<any>;
      config: Node<any>;
      updateEditingConfig: (newConfig: any) => void;
    }>;
  }, [calledRefined, updateEditingConfigurableNode]);

  const isLoading = updatingConfig || isRefining || isExpanding;

  const getEjectPanelConfigUpdate = useCallback(() => {
    let currHandler = handler;
    let currExp: NodeOrVoidNode | EditingNode = exp;
    let currPanelConfig = props.config?.panelConfig;

    while (currHandler != null) {
      const opName = panelIdToPanelOpName(currHandler.id);
      const op = weave.client.opStore.getOpDef(opName);
      if (op == null) {
        break;
      }
      const panelOpConfig = _.omit(currPanelConfig ?? {}, 'childConfig') ?? {};
      currExp = callOpVeryUnsafe(panelIdToPanelOpName(currHandler.id), {
        input: currExp as any,
        config: constNodeUnsafe('any', panelOpConfig),
      });
      currHandler = (currHandler as any).child;
      if (currHandler != null) {
        currPanelConfig = (currPanelConfig ?? {}).childConfig ?? null;
      }
    }
    if (currHandler !== handler) {
      return {
        exp: currExp as any,
        panelId: (currHandler as any)?.id,
        panelConfig: currPanelConfig,
      };
    }
    return {};
  }, [handler, exp, props.config, weave]);

  const panelOptions = useMemo(() => {
    // hard coding this to tables for now - could make more generic in the future
    const handlerCanBePlotted =
      weavePlotEnabled && isTablePanelHandler(handler);
    let results = stackIds.map(si => {
      const isActive =
        handler != null &&
        si.displayName === getStackIdAndName(handler).displayName;
      return {
        text: si.displayName,
        value: si.id,
        key: si.id,
        active: isActive,
        selected: isActive,
      };
    });

    if (handlerCanBePlotted) {
      results = [
        {
          text: 'Plot table query',
          value: PANEL_OPTION_PREFIX.eject + 'plot',
          key: PANEL_OPTION_PREFIX.eject + 'plot',
          active: false,
          selected: false,
        },
        ...results,
      ];
    }
    return results;
  }, [handler, stackIds, weavePlotEnabled]);

  const handlePanelChange = useCallback(
    (
      event: SyntheticEvent<HTMLElement, Event>,
      data: DropdownProps
    ): void | undefined => {
      if (
        data.value == null ||
        getStackIdAndName(handler as any).id === data.value
      ) {
        return;
      } else if (String(data.value).startsWith(PANEL_OPTION_PREFIX.eject)) {
        const newPanelId = String(data.value).slice(
          PANEL_OPTION_PREFIX.eject.length
        );
        updateConfig({...getEjectPanelConfigUpdate(), panelId: newPanelId});
      } else if (
        String(data.value) === 'table' &&
        props.config?.exp.nodeType === 'output' &&
        props.config.exp.fromOp.name === 'panel-table'
      ) {
        // hardcoding this branch for now to handle the table case
        deleteTailPanelOps({
          panelId: String(data.value),
        });
      } else {
        updatePanelId(String(data.value));
      }
    },
    [
      updatePanelId,
      updateConfig,
      handler,
      getEjectPanelConfigUpdate,
      props,
      deleteTailPanelOps,
    ]
  );

  useEffect(() => {
    try {
      const expSpine = makeSpine(inputPath);
      const panelId = handler != null ? getStackIdAndName(handler).id : null;
      if (expSpine != null && panelId != null) {
        trackWeavePanelEvent('expression', {
          panelId,
          expSpine,
        });
      }
    } catch (e) {
      // ignore
    }
  }, [inputPath, handler]);

  const exprAndPanelLocked = !!props.config?.exprAndPanelLocked;

  const toggleExprLock = useCallback(() => {
    updateConfig({exprAndPanelLocked: !exprAndPanelLocked});
  }, [updateConfig, exprAndPanelLocked]);

  return {
    applyEditingConfig,
    calledExpanded,
    config,
    configOpen,
    configurableNodeSettings,
    curPanelName,
    deleteTailPanelOps,
    discardEditingConfig,
    editingConfigIsModified,
    editingPanelConfig,
    expArgsAreModified,
    exprAndPanelLocked,
    getEjectPanelConfigUpdate,
    handlePanelChange,
    handler,
    inputPath,
    isLoading,
    newVars,
    panelOptions,
    refinedExpression,
    renderPanelConfig,
    setConfigOpen,
    toggleExprLock,
    updateConfig,
    updateEditingPanelConfig,
    updateExp,
    updatePanelInput,
    updateRenderPanelConfig,
    updateEditingPanelConfig2,
    updateRenderPanelConfig2,
    weavePlotEnabled,
  };
}
