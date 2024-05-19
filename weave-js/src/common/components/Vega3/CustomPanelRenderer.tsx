import {produce} from 'immer';
import * as _ from 'lodash';
import React, {useMemo, useRef} from 'react';
import ReactDOM from 'react-dom';
import Measure, {BoundingRect} from 'react-measure';
import {SignalListeners, Vega, VisualizationSpec} from 'react-vega';
import {Error as VegaLogLevelError, transforms, View as VegaView} from 'vega';

import {useDeepMemo} from '../../state/hooks';
import * as QueryResult from '../../state/queryGraph/queryResult';
import {printPDFInNewWindow} from '../../util/printPDF';
import {RunColorConfig} from '../../util/section';
import {UserSettings} from '../../util/vega2';
import {
  defaultRunSetsQuery,
  getDefaultViewedRun,
  injectFields,
  parseSpecFields,
  Query,
  specHasBindings,
  updateQueryIndex,
  VIEW_ALL_RUNS,
} from '../../util/vega3';
import PanelError from '../elements/PanelError';
import SliderInput from '../elements/SliderInput';
import {VegaPanel2Config} from '../PanelVega2/common';
import WandbLoader from '../WandbLoader';
import {WBSelect} from '../WBSelect';
import * as S from './CustomPanelRenderer.styles';
import Rasterize from './Rasterize';
import {patchWBVegaSpec} from './vegaSpecPatches';

type PanelExportRef = {
  onDownloadSVG: (name: string) => Promise<void>;
  onDownloadPNG: (name: string) => Promise<void>;
  onDownloadPDF: (name: string) => Promise<void>;
};

transforms.rasterize = Rasterize as any;

const INCOMPLETE_QUERY_MESSAGE =
  'Expression parse error: please check field settings';

function specHasWandbData(spec: VisualizationSpec) {
  if (Array.isArray(spec.data)) {
    for (const table of spec.data) {
      if (table.name.includes('wandb')) {
        return true;
      }
    }
  } else {
    if (typeof spec.data === 'object') {
      if (spec.data?.name === 'wandb') {
        return true;
      }
    }
  }
  return false;
}

export type SingleTableDataType = QueryResult.Row[];
export type MultiTableDataType = {[tableName: string]: SingleTableDataType};
export type CustomPanelRendererDataType =
  | SingleTableDataType
  | MultiTableDataType;

const dataIsSingle = (
  data: CustomPanelRendererDataType
): data is SingleTableDataType => Array.isArray(data);
const dataIsMulti = (
  data: CustomPanelRendererDataType
): data is MultiTableDataType => !dataIsSingle(data);

interface CustomPanelRendererProps {
  spec: VisualizationSpec;
  err?: string | null;
  loading: boolean;
  slow: boolean;
  data: CustomPanelRendererDataType;
  userSettings: UserSettings;
  customRunColors?: RunColorConfig;
  panelExportRef?: React.MutableRefObject<PanelExportRef | undefined>;
  /**
   * For forcing reruns
   */
  innerKey?: string | number;
  /**
   * For the run selector
   */
  showRunSelector?: boolean;
  viewableRunOptions?: string[];
  viewedRun?: string;
  /**
   * for the step selector
   */
  showStepSelector?: boolean;
  viewedStep?: number;
  viewableStepOptions?: number[];
  panelConfig?: VegaPanel2Config;
  signalListeners?: SignalListeners;
  vegaRef?: React.MutableRefObject<Vega | null>;

  // critical width (in pixels) below which legends are hidden. if not specified,
  // legends are not hidden.
  legendCutoffWidth?: number;

  setViewedRun?(runName: string): void;
  setUserQuery?(query: Query): void;
  setView?(view: VegaView | null): void;
  handleTooltip?(handler: any, event: any, item: any, value: any): void;
  onNewView?(view: VegaView): void;
}

function hideLegends(obj: any): any {
  if (_.isArray(obj)) {
    return obj.map(hideLegends);
  } else if (_.isPlainObject(obj)) {
    return _.mapValues(obj, (v, k) => {
      if (k === 'legend') {
        return false;
      }
      return hideLegends(v);
    });
  }
  return obj;
}

const CustomPanelRenderer: React.FC<CustomPanelRendererProps> = props => {
  const {
    spec,
    err,
    loading,
    slow,
    data,
    panelExportRef,
    innerKey,
    showRunSelector,
    viewableRunOptions,
    viewedRun,
    showStepSelector,
    viewedStep,
    viewableStepOptions,
    panelConfig,
    setViewedRun,
    setUserQuery,
    setView,
    handleTooltip,
    signalListeners,
    vegaRef,
    onNewView,
    legendCutoffWidth,
  } = props;

  // Deep memo this so callers don't have to worry about it.
  const userSettings = useDeepMemo(props.userSettings);
  const [dimensions, setDimensions] = React.useState<BoundingRect>();
  const [vegaView, setVegaView] = React.useState<VegaView>();
  const [error, setError] = React.useState<Error>();
  const [showBindings, setShowBindings] = React.useState(false);
  const elRef = useRef<Element>();
  const onError = React.useCallback((e: Error) => {
    setError(e);
  }, []);
  const onNewVegaView = React.useCallback(
    (v: VegaView) => {
      (window as any).VIEW = v;
      setError(undefined);
      setVegaView(v);
      setView?.(v);
      onNewView?.(v);
    },
    [setView, onNewView]
  );

  React.useEffect(() => {
    if (vegaView && dimensions) {
      vegaView.resize();
    }
  }, [dimensions, vegaView]);

  const vegaData = React.useMemo(() => {
    if (dataIsMulti(data)) {
      vegaView?.setState({data});
      return data;
    } else if (
      // viewed run change just changes the filtered data
      // because it does not require a new query
      !viewedRun ||
      !showRunSelector ||
      (viewedRun && viewedRun === VIEW_ALL_RUNS)
    ) {
      vegaView?.setState({data: {wandb: data}});
      return data;
    } else {
      // hack to refresh the data in case vega doesnt do it.
      vegaView?.setState({data: {wandb: []}});
      vegaView?.setState({
        data: {
          wandb: data.filter(row => row.name === viewedRun),
        },
      });
      return data.filter(row => row.name === viewedRun);
    }
  }, [data, viewedRun, showRunSelector, vegaView]);

  const onSliderChange = React.useCallback(
    (value: number) => {
      if (!(panelConfig && viewableStepOptions)) {
        return;
      }
      const newUserQuery = updateQueryIndex(
        panelConfig.userQuery ?? defaultRunSetsQuery,
        viewableStepOptions[value]
      );
      if (setUserQuery) {
        setUserQuery(newUserQuery);
      }
    },
    [panelConfig, setUserQuery, viewableStepOptions]
  );

  React.useEffect(() => {
    if (viewedRun && setViewedRun) {
      setViewedRun(getDefaultViewedRun(viewedRun, viewableRunOptions));
    }
  }, [viewableRunOptions, viewedRun, setViewedRun]);

  const createStepSelectorPortal = React.useCallback(() => {
    const element = elRef.current?.querySelector('.vega-bindings');
    if (element != null && viewableStepOptions != null) {
      return ReactDOM.createPortal(
        <div>
          <SliderInput
            min={0}
            max={viewableStepOptions.length - 1}
            onChange={onSliderChange}
            step={1}
            value={viewableStepOptions.findIndex(val => val === viewedStep)}
          />
          Step: {viewedStep}
        </div>,
        element
      );
    }
    return null;
  }, [onSliderChange, viewableStepOptions, viewedStep]);

  const createRunSelectorPortal = React.useCallback(() => {
    const element = elRef.current?.querySelector('.vega-bindings');
    if (element != null && viewableRunOptions != null) {
      return ReactDOM.createPortal(
        <WBSelect
          options={viewableRunOptions.map(row => {
            return {name: row, value: row};
          })}
          value={viewedRun ?? VIEW_ALL_RUNS}
          onSelect={(value: any) => {
            if (setViewedRun && typeof value === 'string') {
              setViewedRun(value);
            }
          }}
        />,
        element
      );
    }
    return null;
  }, [setViewedRun, viewableRunOptions, viewedRun]);

  let width: number = 0;
  let height: number = 0;
  if (dimensions) {
    width = dimensions.width;
    height = dimensions.height;
  }

  const specWithPatches = useMemo(() => {
    const fieldRefs = parseSpecFields(spec);
    const specWithFields = injectFields(spec, fieldRefs, userSettings);
    const withPatches = patchWBVegaSpec(specWithFields);
    const specWithLegendsMaybeDisabled =
      legendCutoffWidth && width <= legendCutoffWidth
        ? (hideLegends(withPatches) as VisualizationSpec)
        : withPatches;

    return produce(specWithLegendsMaybeDisabled, draft => {
      draft.autosize = {type: 'fit', contains: 'padding'};
    });
  }, [spec, userSettings, width, legendCutoffWidth]);

  const finalData = useMemo(
    () =>
      dataIsSingle(vegaData)
        ? specHasWandbData(specWithPatches)
          ? {wandb: vegaData}
          : undefined
        : vegaData,
    [specWithPatches, vegaData]
  );

  if (err != null) {
    return (
      <S.Wrapper>
        <PanelError className="severe" message={err} />
      </S.Wrapper>
    );
  } else if (_.isEmpty(spec)) {
    // TODO(john): More specific parse errors
    return (
      <S.Wrapper>
        <PanelError className="severe" message="Error: Unable to parse spec" />
      </S.Wrapper>
    );
  }

  const onDownloadSVG = async (name: string): Promise<void> => {
    if (vegaView == null) {
      return;
    }
    try {
      const url = await vegaView.toImageURL('svg');
      clickDownloadLink(url, `${name}.svg`);
    } catch (err) {
      alert(`Error while downloading: ${err}`);
    }
  };

  const onDownloadPNG = async (name: string): Promise<void> => {
    if (vegaView == null) {
      return;
    }
    try {
      const url = await vegaView.toImageURL('png');
      clickDownloadLink(url, `${name}.png`);
    } catch (err) {
      alert(`Error while downloading: ${err}`);
    }
  };

  const onDownloadPDF = async (name: string): Promise<void> => {
    if (vegaView == null) {
      return;
    }
    try {
      const url = await vegaView.toImageURL('svg');
      printPDFInNewWindow(url, name, vegaView.width(), vegaView.height());
    } catch (err) {
      alert(`Error while downloading: ${err}`);
    }
  };

  if (panelExportRef) {
    panelExportRef.current = {
      onDownloadPNG,
      onDownloadSVG,
      onDownloadPDF,
    };
  }

  const hasBindings =
    specHasBindings(spec) ||
    (showRunSelector && viewableRunOptions != null && viewedRun != null) ||
    (showStepSelector && viewableStepOptions != null && viewedStep != null);

  const parseErrorText = 'Expression parse error';

  return (
    <Measure
      bounds
      innerRef={ref => {
        if (ref != null) {
          elRef.current = ref;
        }
      }}
      onResize={contentRect => {
        // Performance hack. Opening the semantic modal may add or remove a
        // scrollbar to the document body. This causes a re-layout, and
        // all panels to resize. Vega panels can be very expensive to resize,
        // so we skip the resize if we're in the background when a modal is
        // open.
        if (dimensions == null) {
          setDimensions(contentRect.bounds);
        } else {
          setTimeout(() => {
            if (elRef.current != null) {
              if (elRef.current.closest('.dimmer') != null) {
                setDimensions(contentRect.bounds);
              } else {
                if (
                  // John: added another hack on this hack :)
                  elRef.current.closest('.custom-panel-editor') != null ||
                  document.querySelector('body.dimmed') == null
                ) {
                  setDimensions(contentRect.bounds);
                }
              }
            }
          }, 100);
        }
      }}>
      {({measureRef}) => {
        return (
          <S.Wrapper ref={measureRef} showBindings={showBindings}>
            {showRunSelector &&
              setViewedRun &&
              viewedRun &&
              viewableRunOptions &&
              createRunSelectorPortal()}
            {showStepSelector &&
              viewableStepOptions &&
              viewedStep != null &&
              setUserQuery &&
              createStepSelectorPortal()}
            {(width > 0 || height > 0) && (
              <Vega
                ref={vegaRef}
                key={innerKey}
                width={width}
                height={height}
                spec={specWithPatches}
                data={finalData}
                actions={false}
                onError={onError}
                onNewView={onNewVegaView}
                tooltip={handleTooltip}
                logLevel={VegaLogLevelError}
                signalListeners={signalListeners}
              />
            )}
            {loading &&
              (slow ? (
                <PanelError
                  message={
                    <>
                      <WandbLoader name="custom-panel-renderer-slow" />
                      <div className="slow-message">
                        This chart is loading very slowly. Change your query to
                        fetch less data.
                      </div>
                    </>
                  }
                />
              ) : (
                <WandbLoader name="custom-panel-renderer" />
              ))}
            {!loading && data.length === 0 && (
              <PanelError message="No data available." />
            )}
            {error && (
              <PanelError
                message={
                  error.message.match(parseErrorText)
                    ? INCOMPLETE_QUERY_MESSAGE
                    : error.name + ': ' + error.message
                }
              />
            )}
            {hasBindings && (
              <S.ToggleBindingsButton
                name={showBindings ? 'close' : 'configuration'}
                onClick={() => setShowBindings(s => !s)}
              />
            )}
          </S.Wrapper>
        );
      }}
    </Measure>
  );
};

export default CustomPanelRenderer;

function clickDownloadLink(url: string, name: string): void {
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('target', '_blank');
  link.setAttribute('download', name);
  link.dispatchEvent(new MouseEvent('click'));
}
