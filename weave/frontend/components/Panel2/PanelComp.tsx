import * as React from 'react';
import {useContext, useState, useMemo, useCallback} from 'react';
// import {ErrorBoundary} from 'react-error-boundary';
import * as Panel2 from './panel';
import * as PanelLib from './panellib/libpanel';
import makeComp from '@wandb/common/util/profiler';
import {Button, Popup, Modal} from 'semantic-ui-react';
import * as Types from '@wandb/cg/browser/model/types';
import {PanelExportUpdaterContext} from './PanelExportContext';
import {ComputeGraphViz} from './ComputeGraphViz';
import * as Op from '@wandb/cg/browser/ops';
import * as CG from '@wandb/cg/browser/graph';
import * as HL from '@wandb/cg/browser/hl';
import * as CGReact from '@wandb/common/cgreact';
import copyToClipboard from 'copy-to-clipboard';
import * as S from './PanelComp.styles';
import {usePanelContext} from './PanelContext';
import _ from 'lodash';
import {EditingOutputNode} from '@wandb/cg/browser/types';
import * as TSTypeWithPath from './tsTypeWithPath';
import Loader from '@wandb/common/components/WandbLoader';
import {WeaveAppContext} from '@wandb/common/cgreact.WeaveAppContext';
import {useDeepMemo} from '@wandb/common/state/hooks';
import {panelSpecById} from './availablePanels';

// For some reason the react-error-page takes 5s to render a single error,
// which is barely ok when you have one error.
// In Panel2 we may have a lot of errors, for example when all table cells
// have an error. When that happens in development, the react-error-page
// tries to render tons of errors, essentially hanging your browser. Set this
// to true to kill react with fire when there is an error, to prevent the hang.
// const STOP_REACT_ERROR_PAGE = true;

interface PanelComp2Props {
  panelSpec: Panel2.PanelSpecNode;
  input: Panel2.PanelInput | Types.NodeOrVoidNode;
  inputType: Types.Type;
  context: Panel2.PanelContext;
  config: any;
  loading?: boolean;
  configMode: boolean;
  noPanelControls?: boolean;
  updateConfig(partialConfig: Partial<any>): void;
  updateContext(partialConfig: Partial<Panel2.PanelContext>): void;
  updateInput?(partialInput: Partial<Panel2.PanelInput>): void;
}

interface PanelCompProps extends PanelComp2Props {
  input: Panel2.PanelInput;
}

interface PanelTransformerCompProps extends PanelCompProps {
  panelSpec: PanelLib.PanelConvertWithChildSpec<
    Panel2.PanelContext,
    any,
    Types.Type
  >;
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

// PanelComp2 is the primary proxy for rendering all Weave Panels.
export const PanelComp2 = makeComp(
  (props: PanelComp2Props) => {
    const {panelSpec, configMode} = props;
    const unboundedContent = useMemo(() => {
      if (panelSpec == null) {
        return <></>;
      }
      if (props.loading) {
        return <Panel2Loader />;
      } else if (
        !PanelLib.isWithChild<Panel2.PanelContext, any, Types.Type>(panelSpec)
      ) {
        if (!configMode) {
          return <panelSpec.Component {...props} />;
        } else if (panelSpec.ConfigComponent != null) {
          return <panelSpec.ConfigComponent {...props} />;
        } else {
          return <></>;
        }
      } else if (
        PanelLib.isTransform<Panel2.PanelContext, any, Types.Type>(panelSpec)
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
          return <panelSpec.Component {...props} child={panelSpec.child} />;
        } else if (panelSpec.ConfigComponent != null) {
          return (
            <panelSpec.ConfigComponent {...props} child={panelSpec.child} />
          );
        } else {
          return <PanelComp2 {...props} panelSpec={panelSpec.child} />;
        }
      }
    }, [props, configMode, panelSpec]);

    if (props.input.nodeType === 'void') {
      return (
        <S.Panel2SizeBoundary>
          <React.Suspense fallback={<Loader />}>
            {unboundedContent}
          </React.Suspense>
        </S.Panel2SizeBoundary>
      );
    }
    return (
      <S.Panel2SizeBoundary>
        {/* <ControlWrapper panelProps={props as PanelCompProps}> */}
        <React.Suspense fallback={<Loader />}>
          {unboundedContent}
        </React.Suspense>
        {/* </ControlWrapper> */}
      </S.Panel2SizeBoundary>
    );
  },
  {id: 'PanelComp2Raw'}
);

const useSplitTransformerConfigs = (
  config: PanelTransformerCompProps['config'],
  updateConfig: PanelTransformerCompProps['updateConfig']
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
  return {baseConfig, updateBaseConfig, childConfig, updateChildConfig};
};

const useTransformerChild = (
  inputNode: Types.Node,
  panelSpec: PanelLib.PanelConvertWithChildSpec<
    Panel2.PanelContext,
    any,
    Types.Type
  >,
  baseConfig: any
): {
  loading: boolean;
  childInputNode: Types.NodeOrVoidNode<Types.Type>;
  childPanelSpec: any;
} => {
  const childPanelSpec = panelSpec.child;
  const newNode = useMemo(() => {
    const result: EditingOutputNode<Types.Type> = HL.callOp(
      Panel2.panelIdToPanelOpName(panelSpec.id),
      {
        input: inputNode,
        config: Op.constNodeUnsafe<'any'>('any', baseConfig),
      }
    );
    return result;
  }, [panelSpec.id, baseConfig, inputNode]);
  const {frame} = usePanelContext();
  const {loading, result: childInputNode} = CGReact.useExpandedNode(
    newNode as any,
    frame
  );

  return {loading, childInputNode, childPanelSpec};
};

export const ConfigTransformerComp = makeComp(
  (props: PanelTransformerCompProps) => {
    const {panelSpec, updateConfig, config} = props;
    const {baseConfig, updateBaseConfig, childConfig, updateChildConfig} =
      useSplitTransformerConfigs(config, updateConfig);
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
  },
  {id: 'ConfigTransformerComp'}
);

export const RenderTransformerComp = makeComp(
  (props: PanelTransformerCompProps) => {
    const {panelSpec, updateConfig, config} = props;
    const {baseConfig, childConfig, updateChildConfig} =
      useSplitTransformerConfigs(config, updateConfig);
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
        panelSpec={childPanelSpec}
      />
    );
  },
  {id: 'RenderTransformerComp'}
);

interface ControlWrapperProps {
  panelProps: PanelCompProps;
}

const ControlWrapper: React.FC<ControlWrapperProps> = ({
  panelProps,
  children,
}) => {
  const {'weave-devpopup': devMode} = useContext(WeaveAppContext);
  const [fullscreen, setFullscreen] = useState(false);
  const [hovering, setHovering] = useState(false);
  const ConfigComponent = panelProps.panelSpec.ConfigComponent;
  const canFullscreen =
    !panelProps.configMode &&
    'canFullscreen' in panelProps.panelSpec &&
    panelProps.panelSpec.canFullscreen;
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

  return showControls ? (
    <S.ControlWrapper
      hovering={hovering}
      onMouseEnter={() => {
        if (!hovering) {
          setHovering(true);
        }
      }}
      onMouseLeave={() => {
        if (hovering) {
          setHovering(false);
        }
      }}
      canFullscreen={canFullscreen}>
      <S.ControlWrapperBar hovering={hovering}>
        {canShowDevQueryPopup && <DevQueryPopup panelProps={panelProps} />}
        {canFullscreen && (
          <S.IconButton
            data-test="panel-fullscreen-button"
            onClick={() => setFullscreen(true)}
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
              <PanelComp2
                {...panelProps}
                noPanelControls
                config={tempConfig}
                updateConfig={updateTempConfig}
              />
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
        {children}
      </S.ControlWrapperContent>
    </S.ControlWrapper>
  ) : (
    <>{children}</>
  );
};
interface DevQueryPopupContentProps {
  panelProps: PanelCompProps;
}
const DevQueryPopupContent: React.FC<DevQueryPopupContentProps> = makeComp(
  props => {
    const [queryVisType, setQueryVisType] = useState<'string' | 'dag'>(
      'string'
    );
    const {panelProps} = props;
    const {addPanel} = useContext(PanelExportUpdaterContext);
    // Note, we simplify here! This means currently exports are simplified!
    const simplifyResult = CGReact.useSimplifiedNode(panelProps.input);
    const node = simplifyResult.loading ? CG.voidNode() : simplifyResult.result;
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
              <pre style={{fontSize: 12}}>{HL.toString(node)}</pre>
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
            copyToClipboard(Types.toString(panelProps.input.type, false))
          }>
          <span style={{fontWeight: 'bold'}}>Input type</span>{' '}
          <pre style={{fontSize: 12}}>
            {Types.toString(panelProps.input.type)}
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
  },
  {id: 'DevQueryPopupContent'}
);

interface DevQueryPopupProps {
  panelProps: PanelCompProps;
}
const DevQueryPopup: React.FC<DevQueryPopupProps> = makeComp(
  props => {
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
  },
  {
    id: 'DevQueryPopup',
  }
);

interface PanelPropsInternal2<I extends Types.Type, C extends {} = {}> {
  input: TSTypeWithPath.TypeToTSTypeWithPath<I>;
  config: C;
  updateConfig(partialConfig: Partial<C>): void;
}

interface PanelPropsExternal2<I extends Types.Type, C extends {} = {}> {
  input: TSTypeWithPath.TypeToTSTypeWithPath<I>;
  config?: C;
  updateConfig?(partialConfig: Partial<C>): void;
}

export function makePanel2Comp<
  I extends Types.Type,
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

  const ConfigProcessingComp: React.FC<PanelPropsInternal2<I, C> & E> =
    props => {
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
        if (
          !processedConfig.loading &&
          processedConfig.config !== props.config
        ) {
          replaceConfig(processedConfig.config);
        }
      }, [
        processedConfig.config,
        processedConfig.loading,
        props,
        replaceConfig,
      ]);
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
  input: Panel2.PanelInput | Types.NodeOrVoidNode;
  config: any;
  updateConfig(partialConfig: Partial<any>): void;
  updateInput?(partialInput: Partial<Panel2.PanelInput>): void;
}> = makeComp(
  props => {
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
        updateInput={props.updateInput}
      />
    );
  },
  {id: 'Panel'}
);

export const PanelConfigEditor: React.FC<{
  panelSpec: Panel2.PanelSpecNode | string;
  input: Panel2.PanelInput | Types.NodeOrVoidNode;
  config: any;
  updateConfig(partialConfig: Partial<any>): void;
  updateInput?(partialInput: Partial<Panel2.PanelInput>): void;
}> = makeComp(
  props => {
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
        updateInput={props.updateInput}
      />
    );
  },
  {id: 'Panel'}
);
