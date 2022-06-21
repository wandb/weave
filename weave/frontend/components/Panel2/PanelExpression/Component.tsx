import * as Types from '@wandb/cg/browser/model/types';
import React, {
  useEffect,
  useContext,
  useState,
  useMemo,
  useCallback,
} from 'react';
import {WeaveAppContext} from '@wandb/common/cgreact.WeaveAppContext';
import * as CGReact from '@wandb/common/cgreact';
import * as HL from '@wandb/cg/browser/hl';
import * as Op from '@wandb/cg/browser/ops';
import {varNode} from '@wandb/cg/browser/ops';
import * as CG from '@wandb/cg/browser/graph';
import {useRefineExpressionEffect} from '../panellib/libexp';
import {EditingNode} from '@wandb/cg/browser/types';
import {usePanelStacksForType, PanelStack} from '../availablePanels';
import * as Panel2 from '../panel';
import {Spec as PanelTableMergeSpec} from '../PanelTableMerge';
import {getStackIdAndName} from '../panellib/libpanel';
import * as _ from 'lodash';
import * as PanelRegistry from '../PanelRegistry';
import {DropdownProps, Button, Menu, Popup, Icon} from 'semantic-ui-react';
import {
  trackWeavePanelEvent,
  makeEventRecorder,
} from '../panellib/libanalytics';
import * as S from '../PanelExpression.styles';
import * as ConfigPanel from '../ConfigPanel';
import Loader from '@wandb/common/components/WandbLoader';
import {PanelComp2} from '../PanelComp';
import {ThemeProvider} from 'styled-components';
import * as QueryEditorStyles from '../ExpressionEditor.styles';
import * as ExpressionEditor from '../ExpressionEditor';
import {
  inputType,
  EMPTY_EXPRESSION_PANEL,
  PanelExpressionConfig,
} from './common';
import {usePrevious} from '@wandb/common/state/hooks';
import {usePanelContext} from '../PanelContext';

const recordEvent = makeEventRecorder('Expression');

type PanelExpressionProps = Panel2.PanelProps<
  typeof inputType,
  PanelExpressionConfig
>;

const PANEL_OPTION_PREFIX = {
  eject: '<Eject>',
};

// Helper function to generate an "english"-friendly name
// to use in the expression.
const useVarNameFromType = (t: Types.Type): string => {
  return useMemo(() => {
    let varName: string = 'x';
    let inputSimpleType = Types.nullableTaggableValue(t);
    // Note: This won't always be correct. Generalize!
    let plural = false;
    if (Types.isListLike(inputSimpleType)) {
      inputSimpleType = Types.nullableTaggableValue(
        Types.listObjectType(inputSimpleType)
      );
      plural = true;
    }
    if (Types.isSimpleType(inputSimpleType)) {
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
    Panel2.isPanelOpName(cExp.fromOp.name ?? '') &&
    // it would be nice to not have to do a refine here.
    _.isEqual(nExp, cExp.fromOp.inputs.input)
  );
}

const isTablePanelHandler = (currHandler: PanelStack | undefined) => {
  return (
    currHandler?.id === 'table' ||
    (currHandler?.id === 'merge' && (currHandler as any)?.child?.id === 'table')
  );
};

function useSynchronizedState<T>(
  obj: T
): [T, React.Dispatch<React.SetStateAction<T>>] {
  const [copy, setCopy] = useState(obj);
  const lastObj = usePrevious(obj);
  useEffect(() => {
    if (lastObj !== obj) {
      setCopy(obj);
    }
  }, [lastObj, obj, setCopy]);

  return [copy, setCopy];
}

const makeSpine = (node: EditingNode<Types.Type>): null | string => {
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
};

const PanelExpression: React.FC<
  Omit<PanelExpressionProps, 'input'> & {
    input: Types.NodeOrVoidNode<typeof inputType>;
  }
> = props => {
  useEffect(() => {
    recordEvent('VIEW');
  }, []);

  const {'lazy-table': lazyTable} = useContext(WeaveAppContext);

  const {updateConfig} = props;
  const inputNode = props.input;
  const refineNode = CGReact.useClientBound(HL.refineNode);
  const [configOpen, setConfigOpen] = useState(false);
  const [updating, setUpdating] = useState(false);
  const config = useMemo(
    () => props.config ?? EMPTY_EXPRESSION_PANEL,
    [props.config]
  );
  // Use a nicer variable name if we can
  const varName = useVarNameFromType(inputNode.type);

  const exp: Types.NodeOrVoidNode<Types.Type> = useMemo(() => {
    if (inputNode.nodeType === 'void') {
      return (config.exp as Types.NodeOrVoidNode) ?? CG.voidNode();
    }
    return config.exp
      ? (HL.mapNodes(
          config.exp,
          node => {
            if (
              node.nodeType === 'var' &&
              (node.type !== inputNode.type || node.varName !== varName)
            ) {
              return varNode(inputNode.type, varName);
            }

            return node;
          },
          true
        ) as Types.NodeOrVoidNode)
      : CG.voidNode();
  }, [config.exp, varName, inputNode]);

  const panelContext = usePanelContext();
  const frame = useMemo(() => {
    if (inputNode.nodeType === 'void') {
      return panelContext.frame;
    } else {
      return {...panelContext.frame, [varName]: inputNode};
    }
  }, [varName, inputNode, panelContext.frame]);

  const {isRefining, refinedExpression} = useRefineExpressionEffect(
    exp as any,
    frame
  );
  const {loading: isExpanding, result: expanded} = CGReact.useExpandedNode(
    refinedExpression,
    frame
  );

  // Call the user's expression. If the expression contains variables that
  // are no longer present in the frame, then the result is void.
  const callNode = useCallback(
    (node: Types.NodeOrVoidNode<Types.Type>) => {
      const withCall =
        node.nodeType !== 'void' ? HL.callFunction(node, frame) : node;
      if (!HL.allVarsWillResolve(withCall, frame)) {
        return CG.voidNode();
      }
      return withCall;
    },
    [frame]
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
      setUpdating(true);
      let currentExp = await refineNode(props.config?.exp as Types.Node, frame);
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
          ...(
            (currentExp as Types.OutputNode).fromOp.inputs
              .config as Types.ConstNode
          ).val,
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
        newExp = (currentExp as Types.OutputNode).fromOp.inputs.input;
      }
      setEditingPanelConfig(currentPanelConfig);
      updateConfig({
        exp: currentExp,
        panelConfig: currentPanelConfig,
        ...(extraConfigUpdate ?? {}),
      });
      setUpdating(false);
    },
    [refineNode, props.config, frame, setEditingPanelConfig, updateConfig]
  );

  const updateExp = useCallback(
    async (newExp: EditingNode) => {
      setUpdating(true);
      if (
        props.config?.exp != null &&
        isUpdateDeletionOfTailPanelOp(
          await refineNode(props.config.exp as Types.Node, frame),
          await refineNode(newExp as Types.Node, frame)
        )
      ) {
        // We just deleted a panelop - we should store it's config on the panel config for consistent UI
        deleteTailPanelOps();
      } else {
        updateConfig({exp: newExp});
      }
      recordEvent('EXP_UPDATE');
      setUpdating(false);
    },
    [updateConfig, props.config, frame, refineNode, deleteTailPanelOps]
  );
  const updatePanelId = useCallback(
    (newPanelId: string | undefined) => {
      updateConfig({panelId: newPanelId});
    },
    [updateConfig]
  );
  const updatePanelInput = useCallback<any>(
    (newInput: Types.Node) => {
      if (refinedExpression.nodeType === 'void') {
        throw new Error(
          'PanelExpression.updatePanelInput: expected refinedExpression.nodeType to be void, found ' +
            refinedExpression.nodeType
        );
      }
      if (
        HL.filterNodes(
          newInput,
          checkNode =>
            checkNode.nodeType === 'var' && checkNode.varName === 'input'
        ).length === 0
      ) {
        console.warn('invalid updateInput call');
        return;
      }
      const newCalled = HL.callFunction(newInput, {
        input: refinedExpression,
      });
      const doUpdate = async () => {
        try {
          const refined = await refineNode(newCalled, frame);
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
    [updateExp, refinedExpression, refineNode, frame]
  );

  const {handler, stackIds} = usePanelStacksForType(
    calledExpanded.type,
    config.panelId,
    {
      excludeMultiTable:
        refinedExpression.nodeType === 'output' &&
        refinedExpression.fromOp.name ===
          Panel2.panelIdToPanelOpName(PanelTableMergeSpec.id),
    }
  );

  const curPanelName =
    handler != null ? getStackIdAndName(handler).displayName : '';

  const [editingExpConfigBase, setEditingExpConfig] =
    useSynchronizedState(refinedExpression);

  const calledRefined = useMemo(
    () => callNode(editingExpConfigBase),
    [callNode, editingExpConfigBase]
  );
  const inputPath = useMemo(
    () => calledExpanded as Types.Node<Types.Type>,
    [calledExpanded]
  );

  // We keep track of the last type that our panel was configured for.
  // If the current handler can't handle that type, then reset the config
  // to {}
  const renderPanelConfig = useMemo(
    () =>
      Types.isAssignableTo2(
        calledExpanded.type,
        config.panelInputType ?? 'void'
      ) ||
      (handler != null &&
        Types.isAssignableTo2(calledExpanded.type, handler.inputType))
        ? config.panelConfig ?? null
        : null,
    [config.panelInputType, config.panelConfig, calledExpanded.type, handler]
  );
  const editingPanelConfig = useMemo(
    () =>
      Types.isAssignableTo2(
        calledExpanded.type,
        config.panelInputType ?? 'void'
      ) ||
      (handler != null &&
        Types.isAssignableTo2(calledExpanded.type, handler.inputType))
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

  const applyEditingConfig = useCallback<any>(() => {
    recordEvent('EDITING_CONFIG_UPDATE');
    updateConfig({
      exp: editingExpConfigBase,
      panelInputType: calledExpanded.type,
      panelConfig: editingPanelConfig,
    });
  }, [
    calledExpanded.type,
    editingPanelConfig,
    updateConfig,
    editingExpConfigBase,
  ]);

  const discardEditingConfig = useCallback<any>(() => {
    setEditingPanelConfig(renderPanelConfig);
    setEditingExpConfig(refinedExpression as any);
  }, [
    renderPanelConfig,
    refinedExpression,
    setEditingPanelConfig,
    setEditingExpConfig,
  ]);

  const expArgsAreModified = useMemo(
    () => !_.isEqual(editingExpConfigBase, refinedExpression),
    [editingExpConfigBase, refinedExpression]
  );

  const editingConfigIsModified = useMemo(
    () =>
      !_.isEqual(renderPanelConfig, editingPanelConfig) || expArgsAreModified,
    [renderPanelConfig, editingPanelConfig, expArgsAreModified]
  );

  const updateEditingConfigurableNode = useCallback(
    async (currentNode: Types.Node<any>, newNode: Types.Node<any>) => {
      const replacedNode = HL.replaceNode(
        editingExpConfigBase,
        currentNode,
        newNode
      );
      setEditingExpConfig(replacedNode as any);
    },
    [editingExpConfigBase, setEditingExpConfig]
  );
  const configurableNodeSettings = useMemo(() => {
    const configurableNodes =
      calledRefined.nodeType === 'void'
        ? []
        : (HL.findChainedAncestors(calledRefined, node => {
            return (
              node.nodeType === 'output' &&
              Panel2.isPanelOpName(node.fromOp.name)
            );
          }) as Array<Types.OutputNode<Types.Type>>);
    return configurableNodes
      .reverse()
      .map(node => {
        const foundPanel = PanelRegistry.ConverterSpecs.find(
          spec => spec.id === Panel2.panelOpNameToPanelId(node.fromOp.name)
        );
        if (foundPanel != null) {
          const keys = Object.keys(node.fromOp.inputs);
          const fromInputNode = node.fromOp.inputs[keys[0]];
          const configNode = node.fromOp.inputs.config;
          return {
            node: fromInputNode,
            panel: foundPanel,
            config: (configNode as Types.ConstNode).val ?? {},
            updateEditingConfig: (newConfig: any) =>
              updateEditingConfigurableNode(
                configNode,
                Op.constNodeUnsafe('any', newConfig)
              ),
          };
        }
        return null;
      })
      .filter(x => x != null) as Array<{
      node: Types.OutputNode<Types.Type>;
      panel: Panel2.PanelConvertSpec<any>;
      config: Types.Node<any>;
      updateEditingConfig: (newConfig: any) => void;
    }>;
  }, [calledRefined, updateEditingConfigurableNode]);

  const isLoading = updating || isRefining || isExpanding;

  const getEjectPanelConfigUpdate = useCallback(() => {
    let currHandler = handler;
    let currExp: Types.NodeOrVoidNode | EditingNode = exp;
    let currPanelConfig = props.config?.panelConfig;

    while (currHandler != null) {
      const opName = Panel2.panelIdToPanelOpName(currHandler.id);
      const op = CG.allGlobalOps()[opName];
      if (op == null) {
        break;
      }
      const panelOpConfig = _.omit(currPanelConfig ?? {}, 'childConfig') ?? {};
      currExp = HL.callOp(Panel2.panelIdToPanelOpName(currHandler.id), {
        input: currExp as any,
        config: Op.constNodeUnsafe('any', panelOpConfig),
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
  }, [handler, exp, props.config]);

  const {'weave-plot': weavePlotEnabled} = useContext(WeaveAppContext);
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
  }, [stackIds, handler, weavePlotEnabled]);

  const handlePanelChange = useCallback(
    (
      event: React.SyntheticEvent<HTMLElement, Event>,
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

  const configurationDom = (
    <S.ConfigurationContent data-test="config-panel">
      <ConfigPanel.ConfigOption label="Render As">
        <ConfigPanel.ModifiedDropdownConfigField
          selection
          disabled={isLoading}
          scrolling
          item
          direction="left"
          options={panelOptions}
          text={curPanelName}
          selectOnBlur={false}
          onChange={handlePanelChange}
          data-test="panel-select"
        />
      </ConfigPanel.ConfigOption>
      <S.ConfigurationContentItems>
        {isLoading ? (
          <Loader />
        ) : (
          <>
            <>
              {configurableNodeSettings.map(
                (
                  {node, panel, config: nodeConfig, updateEditingConfig},
                  ndx
                ) => {
                  return (
                    <S.ConfigurationContentItem key={ndx}>
                      <PanelComp2
                        input={node}
                        inputType={node.type}
                        loading={false}
                        panelSpec={panel as any}
                        configMode={true}
                        context={props.context}
                        config={nodeConfig}
                        updateConfig={updateEditingConfig}
                        updateContext={() => {}}
                      />
                    </S.ConfigurationContentItem>
                  );
                }
              )}
            </>
            <>
              {calledExpanded.nodeType !== 'void' &&
                handler != null &&
                handler?.ConfigComponent != null && (
                  <>
                    {handler.id === 'plot' && weavePlotEnabled && (
                      // Special case for table...
                      // Should make a generic config panel and remove this
                      <S.ConfigurationContentItem>
                        <fieldset style={{borderWidth: '1px'}}>
                          <legend>Table Query</legend>
                          <Button
                            size="tiny"
                            data-test="edit-table-query-button"
                            onClick={() => {
                              deleteTailPanelOps({
                                panelId: 'table',
                              });
                            }}>
                            Edit table query
                          </Button>
                        </fieldset>
                      </S.ConfigurationContentItem>
                    )}
                    <S.ConfigurationContentItem>
                      {expArgsAreModified ? (
                        <span>
                          Please apply above changes before configuring the
                          panel.
                        </span>
                      ) : (
                        <PanelComp2
                          input={inputPath}
                          inputType={calledExpanded.type}
                          loading={false}
                          panelSpec={handler as PanelStack}
                          configMode={true}
                          context={props.context}
                          config={editingPanelConfig}
                          updateConfig={updateEditingPanelConfig}
                          updateContext={props.updateContext}
                        />
                      )}
                    </S.ConfigurationContentItem>
                  </>
                )}
            </>
            <>
              {isTablePanelHandler(handler) && weavePlotEnabled && (
                // Special case for table... Should make a generic
                <S.ConfigurationContentItem>
                  <fieldset style={{borderWidth: '1px'}}>
                    <legend>Table Query</legend>
                    <Button
                      size="tiny"
                      data-test="plot-table-query-button"
                      onClick={() => {
                        updateConfig({
                          ...getEjectPanelConfigUpdate(),
                          panelId: 'plot',
                        });
                      }}>
                      Plot table query
                    </Button>
                  </fieldset>
                </S.ConfigurationContentItem>
              )}
            </>
          </>
        )}
      </S.ConfigurationContentItems>
      <S.ConfigurationContentControls>
        <Button
          color={editingConfigIsModified ? 'red' : undefined}
          disabled={isLoading}
          size="tiny"
          onClick={() => {
            setConfigOpen(false);
            discardEditingConfig();
          }}>
          {editingConfigIsModified ? 'Discard Changes' : 'Close'}
        </Button>
        <div>
          <Button
            size="tiny"
            data-test="apply-panel-config"
            disabled={!editingConfigIsModified || isLoading}
            onClick={() => {
              applyEditingConfig();
            }}>
            Apply
          </Button>
          <Button
            primary
            data-test="ok-panel-config"
            size="tiny"
            disabled={!editingConfigIsModified || isLoading}
            onClick={() => {
              setConfigOpen(false);
              applyEditingConfig();
            }}>
            OK
          </Button>
        </div>
      </S.ConfigurationContentControls>
    </S.ConfigurationContent>
  );

  return (
    <ThemeProvider theme={QueryEditorStyles.themes.light}>
      <S.Main>
        <S.EditorBar style={{pointerEvents: isLoading ? 'none' : 'auto'}}>
          {
            <div style={{width: '100%'}}>
              <Menu
                borderless
                style={{
                  border: 'none',
                  minHeight: '2rem',
                  marginBottom: '2px',
                  borderBottom: '1px solid lightgray',
                  borderRadius: '0px',
                  boxShadow: 'none',
                  padding: '5px',
                }}>
                <Menu.Menu style={{fontSize: '1rem', flex: '1 1 auto'}}>
                  <Menu.Item
                    style={{padding: 0, flex: '1 1 auto'}}
                    disabled={isLoading}>
                    <div
                      style={{width: '100%'}}
                      data-test="panel-expression-expression">
                      <ExpressionEditor.ExpressionEditor
                        frame={frame}
                        node={refinedExpression}
                        updateNode={updateExp}
                        noBox
                        focusOnMount={config.exp == null}
                        disabled={isLoading}
                        disableFreeText={false}
                      />
                    </div>
                  </Menu.Item>
                </Menu.Menu>
                <Menu.Menu position="right" style={{flex: '0 0 auto'}}>
                  <Menu.Item style={{padding: 0}}>
                    <Popup
                      closeOnDocumentClick={false}
                      basic
                      position="right center"
                      popperModifiers={{
                        preventOverflow: {
                          boundary: 'element',
                        },
                      }}
                      popperDependencies={[isLoading]}
                      trigger={
                        <div>
                          <S.ConfigButton
                            disabled={isLoading}
                            data-test="panel-config"
                            style={{
                              padding: '5px',
                            }}>
                            <Icon
                              name="cog"
                              style={{
                                margin: 0,
                                color: configOpen ? '#2e78c7' : 'inherit',
                              }}
                            />
                          </S.ConfigButton>
                        </div>
                      }
                      on="click"
                      open={configOpen}
                      onOpen={() => setConfigOpen(true)}
                      onClose={() => setConfigOpen(false)}>
                      {configurationDom}
                    </Popup>
                  </Menu.Item>
                </Menu.Menu>
              </Menu>
            </div>
          }
        </S.EditorBar>
        <S.PanelHandler lazySusan={lazyTable}>
          <S.PanelHandlerContent>
            {isLoading ? (
              <Loader />
            ) : (
              calledExpanded.nodeType !== 'void' &&
              handler != null && (
                <PanelComp2
                  input={inputPath}
                  inputType={calledExpanded.type}
                  loading={false}
                  panelSpec={handler as PanelStack}
                  configMode={false}
                  context={props.context}
                  config={renderPanelConfig}
                  updateConfig={updateRenderPanelConfig}
                  updateContext={props.updateContext}
                  updateInput={updatePanelInput}
                  noPanelControls
                />
              )
            )}
          </S.PanelHandlerContent>
        </S.PanelHandler>
      </S.Main>
    </ThemeProvider>
  );
};

export default PanelExpression;
