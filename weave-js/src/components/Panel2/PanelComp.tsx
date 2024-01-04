// import {ErrorBoundary} from 'react-error-boundary';
import {datadogRum} from '@datadog/browser-rum';
import {
  callOpVeryUnsafe,
  constNodeUnsafe,
  defaultLanguageBinding,
  EditingOutputNode,
  Node,
  NodeOrVoidNode,
  Type,
  voidNode,
} from '@wandb/weave/core';
import copyToClipboard from 'copy-to-clipboard';
import _ from 'lodash';
import React, {useCallback, useContext, useMemo, useRef, useState} from 'react';
import {Button, Modal, Popup} from 'semantic-ui-react';

import {WeaveApp} from '../..';
import {
  useWeaveErrorBoundaryInPanelComp2Enabled,
  useWeaveFeaturesContext,
} from '../../context';
// import {useExpressionHoverHandlers} from './PanelContext';
import {useWeaveContext} from '../../context';
import {weaveErrorToDDPayload} from '../../errors';
import {useDeepMemo} from '../../hookUtils';
import * as CGReact from '../../react';
import {ErrorPanel} from '../ErrorPanel';
import {panelSpecById} from './availablePanels';
import {ComputeGraphViz} from './ComputeGraphViz';
import * as Panel2 from './panel';
import * as S from './PanelComp.styles';
import {usePanelContext} from './PanelContext';
import {PanelExportUpdaterContext} from './PanelExportContext';
import * as PanelLib from './panellib/libpanel';
import {HOVER_DELAY_MS} from './Tooltip';
import * as TSTypeWithPath from './tsTypeWithPath';

class PanelCompErrorBoundary extends React.Component<
  {
    inPanelMaybe: boolean;
    weave: WeaveApp;
    onInvalidGraph?: (node: NodeOrVoidNode) => void;
  },
  {hasError: boolean; customMessage?: string}
> {
  static getDerivedStateFromError(error: any) {
    // Update state so the next render will show the fallback UI.
    if (error instanceof CGReact.InvalidGraph) {
      return {
        hasError: true,
        customMessage: `Evaluation error: ${error.message}`,
      };
    }
    return {hasError: true};
  }
  constructor(props: any) {
    super(props);
    this.state = {hasError: false};
  }

  componentDidCatch(error: any, errorInfo: any) {
    if (error instanceof CGReact.NullResult && this.props.inPanelMaybe) {
      throw error;
    }

    datadogRum.addAction(
      'weave_panel_error_boundary',
      weaveErrorToDDPayload(error, this.props.weave)
    );

    if (error instanceof CGReact.InvalidGraph) {
      this.props.onInvalidGraph?.(error.node);
      return;
    }
    // You can also log the error to an error reporting service
    // logErrorToMyService(error, errorInfo);
    // onAppError(
    //   'Error: ' +
    //     error.stack +
    //     '\nReact Component Stack: ' +
    //     errorInfo['componentStack']
    // );
  }

  componentDidUpdate(prevProps: any) {
    if (prevProps.children !== this.props.children && this.state.hasError) {
      this.setState({hasError: false, customMessage: undefined});
    }
  }

  render() {
    if (this.state.hasError) {
      return <ErrorPanel title={this.state.customMessage} />;
    }

    return this.props.children;
  }
}

// For some reason the react-error-page takes 5s to render a single error,
// which is barely ok when you have one error.
// In Panel2 we may have a lot of errors, for example when all table cells
// have an error. When that happens in development, the react-error-page
// tries to render tons of errors, essentially hanging your browser. Set this
// to true to kill react with fire when there is an error, to prevent the hang.
// const STOP_REACT_ERROR_PAGE = true;

interface PanelComp2Props {
  panelSpec: Panel2.PanelSpecNode;
  input: Panel2.PanelInput | NodeOrVoidNode;
  inputType: Type;
  context: Panel2.PanelContext;
  config: any;
  loading?: boolean;
  configMode: boolean;
  noPanelControls?: boolean;
  updateConfig(partialConfig: Partial<any>): void;
  updateConfig2?(change: (oldConfig: any) => Partial<any>): void;
  updateContext(partialConfig: Partial<Panel2.PanelContext>): void;
  updateInput?(partialInput: Partial<Panel2.PanelInput>): void;
}

interface PanelCompProps extends PanelComp2Props {
  input: Panel2.PanelInput;
}

interface PanelTransformerCompProps extends PanelCompProps {
  panelSpec: PanelLib.PanelConvertWithChildSpec<Panel2.PanelContext, any, Type>;
}

// function ErrorFallback(props: {error?: Error}) {
//   if (STOP_REACT_ERROR_PAGE && (envIsDev || envIsIntegration)) {
//     ReactDOM.unmountComponentAtNode(document.getElementById('root') as any);
//     ReactDOM.render(
//       <div style={{padding: 24}}>
//         {'W&B Dev: Killed react to prevent hanging error page.'}
//       </div>,
//       document.getElementById('root')
//     );
//   }
//   const {error} = props;
//   return (
//     <div role="alert">
//       <p>Something went wrong</p>
//       <pre>{error?.message}</pre>
//     </div>
//   );
// }

interface PanelCompContextState {
  panelPath: string[];
}

export const PanelCompContext = React.createContext<PanelCompContextState>({
  panelPath: [],
});
PanelCompContext.displayName = 'PanelCompContext';

interface PanelFullscreenContextState {
  isFullscreen: boolean;
  goFullscreen: () => void;
}

export const PanelFullscreenContext =
  React.createContext<PanelFullscreenContextState>({
    isFullscreen: false,
    goFullscreen: () => {
      // console.log('goFullscreen not implemented');
    },
  });
PanelFullscreenContext.displayName = 'PanelFullscreenContext';

const PanelComp2Component = (props: PanelComp2Props) => {
  const ctx = useContext(PanelCompContext);

  return (
    <PanelCompContext.Provider
      value={{panelPath: ctx.panelPath.concat(props.panelSpec.id)}}>
      <PanelComp2Inner {...props} />
    </PanelCompContext.Provider>
  );
};

export const PanelComp2 = React.memo(PanelComp2Component);

export function useUpdateConfig2<C>(props: {
  // config?: PanelComp2Props['config'];
  // updateConfig: PanelComp2Props['updateConfig'];
  // updateConfig2?: PanelComp2Props['updateConfig2'] | undefined;
  config?: C;
  updateConfig(partialConfig: Partial<C>): void;
  updateConfig2?(change: (oldConfig: C) => Partial<C>): void;
}) {
  const {config, updateConfig} = props;

  // By using a ref, we can ensure that downstream components can call
  // updateConfig2 multiple times between re-renders, and the config will
  // always be the latest.

  const workingConfig = useRef(config);
  workingConfig.current = config;
  let {updateConfig2} = props;
  if (updateConfig2 == null) {
    // We selectively add this hook. This is safe to do since updateConfig2 will
    // always either be present or not, for this component.
    // Its important to do it this way, so that if updateConfig2 does exist, we
    // just use it directly. The value of updateConfig2 is it doesn't close over
    // config, so it doesn't change when config changes.
    // eslint-disable-next-line react-hooks/rules-of-hooks
    updateConfig2 = useCallback(
      (change: (oldConfig: any) => any) => {
        const newConfig = change(workingConfig.current);
        workingConfig.current = newConfig;
        updateConfig(newConfig);
      },
      [updateConfig]
    );
  }
  return updateConfig2!;
}

// PanelComp2 is the primary proxy for rendering all Weave Panels.
export const PanelComp2Inner = (props: PanelComp2Props) => {
  const enableErrorBoundary = useWeaveErrorBoundaryInPanelComp2Enabled();
  const {panelSpec, configMode} = props;
  const updateConfig2 = useUpdateConfig2(props);
  let unboundedContent = useMemo(() => {
    if (panelSpec == null) {
      return <></>;
    }
    if (props.loading) {
      return <Panel2Loader />;
    } else if (
      !PanelLib.isWithChild<Panel2.PanelContext, any, Type>(panelSpec)
    ) {
      if (!configMode) {
        return (
          <panelSpec.Component {...props} updateConfig2={updateConfig2!} />
        );
      } else if (panelSpec.ConfigComponent != null) {
        return (
          <panelSpec.ConfigComponent
            {...props}
            updateConfig2={updateConfig2!}
          />
        );
      } else {
        return <></>;
      }
    } else if (
      PanelLib.isTransform<Panel2.PanelContext, any, Type>(panelSpec)
    ) {
      if (!configMode) {
        return (
          <RenderTransformerComp {...(props as PanelTransformerCompProps)} />
        );
      } else {
        return (
          <ConfigTransformerComp {...(props as PanelTransformerCompProps)} />
        );
      }
    } else {
      if (!configMode) {
        return (
          <panelSpec.Component
            {...props}
            child={panelSpec.child}
            updateConfig2={updateConfig2!}
          />
        );
      } else if (panelSpec.ConfigComponent != null) {
        return (
          <panelSpec.ConfigComponent
            {...props}
            child={panelSpec.child}
            updateConfig2={updateConfig2!}
          />
        );
      } else {
        return <PanelComp2 {...props} panelSpec={panelSpec.child} />;
      }
    }
  }, [panelSpec, props, configMode, updateConfig2]);

  const {panelMaybeNode} = usePanelContext();
  const weave = useWeaveContext();

  unboundedContent = useMemo(() => {
    return enableErrorBoundary ? (
      <PanelCompErrorBoundary
        inPanelMaybe={panelMaybeNode != null}
        weave={weave}>
        {unboundedContent}
      </PanelCompErrorBoundary>
    ) : (
      unboundedContent
    );
  }, [enableErrorBoundary, panelMaybeNode, unboundedContent, weave]);

  if (props.input.nodeType === 'void') {
    return (
      <S.Panel2SizeBoundary>
        <React.Suspense fallback={<Panel2Loader />}>
          {unboundedContent}
        </React.Suspense>
      </S.Panel2SizeBoundary>
    );
  }
  return (
    <S.Panel2SizeBoundary>
      <ControlWrapper panelProps={props as PanelCompProps}>
        <React.Suspense fallback={<Panel2Loader />}>
          {unboundedContent}
        </React.Suspense>
      </ControlWrapper>
    </S.Panel2SizeBoundary>
  );
};

const useSplitTransformerConfigs = (
  config: PanelTransformerCompProps['config'],
  updateConfig: PanelTransformerCompProps['updateConfig'],
  updateConfig2: PanelTransformerCompProps['updateConfig2']
) => {
  config = useMemo(() => config ?? {}, [config]);
  const baseConfig = useDeepMemo(_.omit(config, 'childConfig'));
  const childConfig = useMemo(
    () => config.childConfig ?? {},
    [config.childConfig]
  );

  const updateBaseConfig = useCallback(
    newConfig =>
      updateConfig({
        ...newConfig,
        childConfig,
      }),
    [updateConfig, childConfig]
  );

  const updateChildConfig = useCallback(
    newConfig =>
      updateConfig({
        ...config,
        childConfig: {
          ...childConfig,
          ...newConfig,
        },
      }),
    [updateConfig, config, childConfig]
  );

  const incomingUpdateConfig2 = useMemo(() => {
    if (updateConfig2 == null) {
      return undefined;
    }
    return (childChangeFunction: (oldChildConfig: any) => Partial<any>) => {
      const parentChangeFunction = (oldParentConfig: any) => {
        return {
          ...oldParentConfig,
          childConfig: childChangeFunction(oldParentConfig.childConfig),
        };
      };
      updateConfig2(parentChangeFunction);
    };
  }, [updateConfig2]);

  const updateChildConfig2 = useUpdateConfig2({
    config: childConfig,
    updateConfig: updateChildConfig,
    updateConfig2: incomingUpdateConfig2,
  });
  return {
    baseConfig,
    updateBaseConfig,
    childConfig,
    updateChildConfig,
    updateChildConfig2,
  };
};

const useTransformerChild = (
  inputNode: Node,
  panelSpec: PanelLib.PanelConvertWithChildSpec<Panel2.PanelContext, any, Type>,
  baseConfig: any
): {
  loading: boolean;
  childInputNode: NodeOrVoidNode<Type>;
  childPanelSpec: any;
} => {
  const childPanelSpec = panelSpec.child;
  const newNode = useMemo(() => {
    const result: EditingOutputNode<Type> = callOpVeryUnsafe(
      Panel2.panelIdToPanelOpName(panelSpec.id),
      {
        input: inputNode,
        config: constNodeUnsafe<'any'>('any', baseConfig),
      }
    );
    return result;
  }, [panelSpec.id, baseConfig, inputNode]);
  const {loading, result: childInputNode} = CGReact.useExpandedNode(
    newNode as any
  );

  return {loading, childInputNode, childPanelSpec};
};

export const ConfigTransformerComp = (props: PanelTransformerCompProps) => {
  const {panelSpec, updateConfig, config} = props;
  const updateConfig2 = useUpdateConfig2(props);
  const {baseConfig, updateBaseConfig, childConfig, updateChildConfig} =
    useSplitTransformerConfigs(config, updateConfig, updateConfig2);
  const {loading, childInputNode, childPanelSpec} = useTransformerChild(
    props.input,
    panelSpec,
    baseConfig
  );

  return (
    <>
      {panelSpec.ConfigComponent != null && (
        <panelSpec.ConfigComponent
          {...props}
          config={baseConfig}
          child={childPanelSpec}
          updateConfig={updateBaseConfig}
          updateConfig2={updateConfig2}
        />
      )}
      <PanelComp2
        {...props}
        input={childInputNode}
        loading={loading}
        inputType={childInputNode.type}
        config={childConfig}
        updateConfig={updateChildConfig}
        panelSpec={childPanelSpec}
      />
    </>
  );
};

export const RenderTransformerComp = (props: PanelTransformerCompProps) => {
  const {panelSpec, updateConfig, config, updateConfig2} = props;
  const {baseConfig, childConfig, updateChildConfig, updateChildConfig2} =
    useSplitTransformerConfigs(config, updateConfig, updateConfig2);
  const {loading, childInputNode, childPanelSpec} = useTransformerChild(
    props.input,
    panelSpec,
    baseConfig
  );

  return (
    <PanelComp2
      {...props}
      input={childInputNode}
      loading={loading}
      inputType={childInputNode.type}
      config={childConfig}
      updateConfig={updateChildConfig}
      updateConfig2={updateChildConfig2}
      panelSpec={childPanelSpec}
    />
  );
};

interface ControlWrapperProps {
  panelProps: PanelCompProps;
}

const shouldEnableFullscreen = _.memoize(
  (
    panelPath: string[],
    canFullscreen: boolean,
    parentIsFullscreen: boolean,
    configMode: boolean
  ): boolean => {
    // If panel can't be fullscreened, never enable fullscreen controls
    if (!canFullscreen) {
      return false;
    }

    // If panel is in config mode, never enable fullscreen controls
    if (configMode) {
      return false;
    }

    let panelAncestry = panelPath.slice(0, -1).reverse();

    // Get the panel path up to the closest table ancestor
    const tableAncestorIndex = panelAncestry.findIndex(id => id === 'table');

    if (tableAncestorIndex !== -1) {
      panelAncestry = panelAncestry.slice(0, tableAncestorIndex + 1);
    }

    // If ancestors include PanelRow, disable fullscreen,
    // unless parent is fullscreen, in which case we want to
    // enable fullscreen so that we can have nested fullscreen modals
    if (panelAncestry.some(id => id === 'row') && !parentIsFullscreen) {
      return false;
    }

    return true;
  },
  (panelPath, canFullscreen, parentIsFullscreen, configMode) =>
    `${panelPath.join(
      ':'
    )}|${configMode}|${canFullscreen}|${parentIsFullscreen}`
);

const ControlWrapper: React.FC<ControlWrapperProps> = ({
  panelProps,
  children,
}) => {
  const devMode = useWeaveFeaturesContext().betaFeatures['weave-devpopup'];
  const fullscreenContext = useContext(PanelFullscreenContext);
  const {isFullscreen: parentIsFullscreen} = fullscreenContext;
  const {panelPath} = useContext(PanelCompContext);

  const [fullscreen, setFullscreen] = useState(false);

  const [hovering, setHovering] = useState(false);
  const hoverTimeoutIDRef = useRef<number | null>(null);
  const onHover = useCallback(() => {
    const timeoutID = window.setTimeout(() => {
      if (hoverTimeoutIDRef.current !== timeoutID) {
        return;
      }
      setHovering(true);
    }, HOVER_DELAY_MS);
    hoverTimeoutIDRef.current = timeoutID;
  }, []);
  const onUnhover = useCallback(() => {
    setHovering(false);
    hoverTimeoutIDRef.current = null;
  }, []);

  const ConfigComponent = panelProps.panelSpec.ConfigComponent;
  const canFullscreen = shouldEnableFullscreen(
    panelPath,
    panelProps.panelSpec.canFullscreen ?? false,
    parentIsFullscreen,
    panelProps.configMode
  );
  const canShowDevQueryPopup = devMode && !panelProps.configMode;
  const showControls =
    !panelProps.noPanelControls && (canFullscreen || canShowDevQueryPopup);
  const [tempConfig, setTempConfig] = useState(panelProps.config);
  const updateTempConfig = useCallback(
    (newConfig: any) => {
      setTempConfig({...tempConfig, ...newConfig});
    },
    [setTempConfig, tempConfig]
  );
  const onClose = useCallback(() => {
    if (tempConfig !== panelProps.config) {
      panelProps.updateConfig(tempConfig);
    }
    setFullscreen(false);
  }, [tempConfig, panelProps]);

  const goFullscreen = useMemo(() => {
    if (!canFullscreen) {
      return fullscreenContext.goFullscreen;
    }
    return () => {
      setFullscreen(true);
    };
  }, [canFullscreen, fullscreenContext.goFullscreen]);

  return showControls || fullscreen ? (
    <S.ControlWrapper
      hovering={hovering}
      onMouseEnter={() => {
        // onExpressionHover();
        onHover();
      }}
      onMouseLeave={() => {
        // onExpressionUnhover();
        onUnhover();
      }}
      canFullscreen={canFullscreen}>
      <S.ControlWrapperBar hovering={hovering}>
        {canShowDevQueryPopup && <DevQueryPopup panelProps={panelProps} />}
        {canFullscreen && (
          <S.IconButton
            data-test="panel-fullscreen-button"
            onClick={ev => {
              ev.stopPropagation();
              setFullscreen(true);
              setHovering(false);
            }}
            style={{cursor: 'pointer'}}>
            <S.FullscreenButton />
          </S.IconButton>
        )}
      </S.ControlWrapperBar>
      <S.ControlWrapperContent canFullscreen={canFullscreen}>
        <Modal
          open={fullscreen}
          size={'fullscreen'}
          onClose={onClose}
          onOpen={() => setFullscreen(true)}>
          <Modal.Content
            style={{
              height: 'calc(90vh - 73px)',
              overflow: 'hidden',
              display: 'flex',
            }}>
            <div
              style={{
                flex: '1 1 auto',
                marginRight: '30px',
              }}>
              <PanelFullscreenContext.Provider
                value={{isFullscreen: fullscreen, goFullscreen}}>
                <PanelComp2
                  {...panelProps}
                  noPanelControls
                  config={tempConfig}
                  updateConfig={updateTempConfig}
                />
              </PanelFullscreenContext.Provider>
            </div>
            {ConfigComponent != null && (
              <div
                style={{
                  flex: '0 0 300px',
                }}>
                <PanelComp2
                  {...panelProps}
                  noPanelControls
                  configMode
                  config={tempConfig}
                  updateConfig={updateTempConfig}
                />
              </div>
            )}
          </Modal.Content>
          <Modal.Actions>
            <Button
              data-test="panel-fullscreen-modal-close-button"
              onClick={onClose}>
              Close
            </Button>
          </Modal.Actions>
        </Modal>
        <PanelFullscreenContext.Provider
          value={{isFullscreen: fullscreen, goFullscreen}}>
          {children}
        </PanelFullscreenContext.Provider>
      </S.ControlWrapperContent>
    </S.ControlWrapper>
  ) : (
    <S.ControlWrapper hovering={false}>
      <PanelFullscreenContext.Provider
        value={{isFullscreen: parentIsFullscreen, goFullscreen}}>
        {children}
      </PanelFullscreenContext.Provider>
    </S.ControlWrapper>
  );
};
interface DevQueryPopupContentProps {
  panelProps: PanelCompProps;
}
const DevQueryPopupContent: React.FC<DevQueryPopupContentProps> = props => {
  const weave = useWeaveContext();
  const [queryVisType, setQueryVisType] = useState<'string' | 'dag'>('string');
  const {panelProps} = props;
  const {addPanel} = useContext(PanelExportUpdaterContext);
  // Note, we simplify here! This means currently exports are simplified!
  const simplifyResult = CGReact.useSimplifiedNode(panelProps.input);
  const node = simplifyResult.loading ? voidNode() : simplifyResult.result;
  return (
    <div
      style={{
        maxHeight: 600,
        maxWidth: 600,
        overflow: 'auto',
        fontSize: 14,
        whiteSpace: 'nowrap',
      }}>
      <div>
        <span>
          <span style={{fontWeight: 'bold', marginRight: 8}}>Query</span>
          <span
            style={{
              cursor: 'pointer',
              borderBottom:
                queryVisType === 'string' ? '1px solid #888' : undefined,
            }}
            onClick={() => setQueryVisType('string')}>
            string
          </span>
          {' | '}
          <span
            style={{
              cursor: 'pointer',
              borderBottom:
                queryVisType === 'dag' ? '1px solid #888' : undefined,
            }}
            onClick={() => setQueryVisType('dag')}>
            dag
          </span>
        </span>{' '}
        {node != null ? (
          queryVisType === 'string' ? (
            <pre style={{fontSize: 12}}>{weave.expToString(node)}</pre>
          ) : (
            <ComputeGraphViz node={node} width={600} height={300} />
          )
        ) : (
          // <ComputeGraphViz node={node} width={600} height={300} />
          <span>TODO: Node not available</span>
        )}
      </div>
      <div
        onClick={() =>
          copyToClipboard(
            defaultLanguageBinding.printType(panelProps.input.type, false)
          )
        }>
        <span style={{fontWeight: 'bold'}}>Input type</span>{' '}
        <pre style={{fontSize: 12}}>
          {defaultLanguageBinding.printType(panelProps.input.type)}
        </pre>
      </div>
      <div>
        <span style={{fontWeight: 'bold'}}>Panel</span>{' '}
        {panelProps.panelSpec.id}
      </div>
      {panelProps.config != null && (
        <div>
          <span style={{fontWeight: 'bold'}}>Config</span>{' '}
          {JSON.stringify(panelProps.config, undefined, 2)}
        </div>
      )}
      <Button
        style={{marginTop: 16, padding: '4px 8px'}}
        onClick={() => {
          addPanel({
            node,
            panelId: PanelLib.getStackIdAndName(panelProps.panelSpec).id,
            config: panelProps.config,
          });
        }}>
        New query
      </Button>
    </div>
  );
};

interface DevQueryPopupProps {
  panelProps: PanelCompProps;
}
const DevQueryPopup: React.FC<DevQueryPopupProps> = props => {
  const [open, setOpen] = useState(false);
  const {panelProps} = props;
  return (
    <Popup
      trigger={
        // we need the <span> so that Popup can find the position of IconButton when it's wrapped
        // in a styled component -- tried <Ref> but it didn't work
        <span>
          <S.IconButton>
            <S.DevQueryIcon style={{transform: 'translateY(-4px)'}} />
          </S.IconButton>
        </span>
      }
      open={open}
      onOpen={() => setOpen(true)}
      onClose={() => setOpen(false)}
      hoverable
      content={open && <DevQueryPopupContent panelProps={panelProps} />}
    />
  );
};

interface PanelPropsInternal2<I extends Type, C extends {} = {}> {
  input: TSTypeWithPath.TypeToTSTypeWithPath<I>;
  config: C;
  updateConfig(partialConfig: Partial<C>): void;
}

interface PanelPropsExternal2<I extends Type, C extends {} = {}> {
  input: TSTypeWithPath.TypeToTSTypeWithPath<I>;
  config?: C;
  updateConfig?(partialConfig: Partial<C>): void;
}

export function makePanel2Comp<
  I extends Type,
  C extends {} = {},
  E extends {} = {}
>(
  InternalComp: React.FC<PanelPropsInternal2<I, C> & E>,
  useProcessedConfig: (
    input: TSTypeWithPath.TypeToTSTypeWithPath<I>,
    config?: any
  ) => {loading: boolean; config: C} = (input, config) => ({
    loading: false,
    config,
  })
): React.FC<PanelPropsExternal2<I, C> & E> {
  const ExternalComp: React.FC<PanelPropsExternal2<I, C> & E> = props => {
    if (props.input == null) {
      throw new Error('missing input');
    }

    if (props.config == null && props.updateConfig != null) {
      throw new Error('missing config');
    }

    const defaultBackupConfig = React.useMemo(
      () => props.config ?? {},
      [props.config]
    );

    const [backupConfig, updateBackupConfig] =
      Panel2.useConfig(defaultBackupConfig);

    const internalProps = React.useMemo(() => {
      return {
        config: props.config != null ? props.config : backupConfig,
        updateConfig:
          props.updateConfig != null ? props.updateConfig : updateBackupConfig,
      };
    }, [backupConfig, props.config, props.updateConfig, updateBackupConfig]);

    return <ConfigProcessingComp {...props} {...internalProps} />;
  };

  const ConfigProcessingComp: React.FC<
    PanelPropsInternal2<I, C> & E
  > = props => {
    const {updateConfig: propsUpdateConfig, config: propsConfig} = props;
    const processedConfig = useProcessedConfig(props.input, props.config);
    const replaceConfig = React.useCallback(
      (newConfig: C) => {
        propsUpdateConfig({
          ..._.mapValues(propsConfig, () => undefined),
          ...newConfig,
        });
      },
      [propsConfig, propsUpdateConfig]
    );
    const updateProcessedConfig = React.useCallback(
      (update: Partial<C>) => {
        if (!processedConfig.loading) {
          if (processedConfig.config === propsConfig) {
            propsUpdateConfig(update);
          } else {
            replaceConfig({...processedConfig.config, ...update});
          }
        }
      },
      [
        processedConfig.config,
        processedConfig.loading,
        propsConfig,
        propsUpdateConfig,
        replaceConfig,
      ]
    );
    React.useEffect(() => {
      if (!processedConfig.loading && processedConfig.config !== props.config) {
        replaceConfig(processedConfig.config);
      }
    }, [processedConfig.config, processedConfig.loading, props, replaceConfig]);
    return (
      <InternalComp
        {...props}
        config={processedConfig.config}
        updateConfig={updateProcessedConfig}
      />
    );
  };

  return ExternalComp;
}

export const Panel2Loader: React.FC = () => {
  return <S.Panel2LoaderStyle data-test="loader" />;
};

// This is a wrapper around the older PanelComp2, which is
// much more convenient to use.
//
// First, it drops legacy props that are no longer needed.
//
// It also forces configMode to false.
// We'll create a separate ConfigEditor component for
// configMode = True
//
// And it accepts either a PanelStack or a string panelId as in
// the panelSpec parameter
export const Panel: React.FC<{
  panelSpec: Panel2.PanelSpecNode | string;
  input: Panel2.PanelInput | NodeOrVoidNode;
  config?: any;
  updateConfig(partialConfig: Partial<any>): void;
  updateConfig2?(change: (oldConfig: any) => any): void;
  updateInput?(partialInput: Partial<Panel2.PanelInput>): void;
}> = props => {
  const panelSpec = useMemo(
    () =>
      typeof props.panelSpec === 'string'
        ? panelSpecById(props.panelSpec)
        : props.panelSpec,
    [props.panelSpec]
  );
  const PC2 = PanelComp2 as React.FC<any>;
  return (
    <PC2
      input={props.input}
      panelSpec={panelSpec}
      configMode={false}
      config={props.config}
      updateConfig={props.updateConfig}
      updateConfig2={props.updateConfig2}
      updateInput={props.updateInput}
    />
  );
};

export const PanelConfigEditor: React.FC<{
  panelSpec: Panel2.PanelSpecNode | string;
  input: Panel2.PanelInput | NodeOrVoidNode;
  config: any;
  updateConfig(partialConfig: Partial<any>): void;
  updateConfig2?(change: (oldConfig: any) => any): void;
  updateInput?(partialInput: Partial<Panel2.PanelInput>): void;
}> = props => {
  const panelSpec = useMemo(
    () =>
      typeof props.panelSpec === 'string'
        ? panelSpecById(props.panelSpec)
        : props.panelSpec,
    [props.panelSpec]
  );

  const PC2 = PanelComp2 as React.FC<any>;
  return (
    <PC2
      input={props.input}
      panelSpec={panelSpec}
      configMode={true}
      config={props.config}
      updateConfig={props.updateConfig}
      updateConfig2={props.updateConfig2}
      updateInput={props.updateInput}
    />
  );
};
export const TransactionalPanelConfigEditor: React.FC<{
  panelSpec: Panel2.PanelSpecNode | string;
  input: Panel2.PanelInput | NodeOrVoidNode;
  config: any;
  updateConfig(partialConfig: Partial<any>): void;
  updateConfig2?(change: (oldConfig: any) => any): void;
  updateInput?(partialInput: Partial<Panel2.PanelInput>): void;
}> = props => {
  const panelSpec = useMemo(
    () =>
      typeof props.panelSpec === 'string'
        ? panelSpecById(props.panelSpec)
        : props.panelSpec,
    [props.panelSpec]
  );

  const [pendingConfig, setPendingConfig] = useState(props.config);
  const [configIsModified, setConfigIsModified] = useState(false);

  const {updateConfig} = props;
  const proxiedUpdateConfig = useCallback(
    (partialConfig: Partial<any>) => {
      setConfigIsModified(true);
      setPendingConfig(partialConfig);
    },
    [setPendingConfig, setConfigIsModified]
  );

  const applyPendingConfig = useCallback(() => {
    setConfigIsModified(false);
    updateConfig(pendingConfig);
  }, [updateConfig, pendingConfig]);

  return (
    <div data-test="config-panel">
      <PanelConfigEditor
        input={props.input}
        panelSpec={props.panelSpec}
        config={pendingConfig}
        updateConfig={proxiedUpdateConfig}
        updateConfig2={props.updateConfig2}
        updateInput={props.updateInput}
      />
      {panelSpec?.ConfigComponent != null && (
        <div style={{margin: '5px 0px'}}>
          <Button
            primary
            size="tiny"
            data-test="apply-panel-config"
            disabled={!configIsModified}
            onClick={() => {
              applyPendingConfig();
            }}>
            Apply
          </Button>
        </div>
      )}
    </div>
  );
};
