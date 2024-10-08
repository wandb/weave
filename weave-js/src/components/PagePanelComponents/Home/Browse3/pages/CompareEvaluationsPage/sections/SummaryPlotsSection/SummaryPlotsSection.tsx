import {Box} from '@material-ui/core';
import {Popover} from '@mui/material';
import {Switch} from '@wandb/weave/components';
import {Button} from '@wandb/weave/components/Button';
import {
  DraggableGrow,
  DraggableHandle,
} from '@wandb/weave/components/DraggablePopups';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {maybePluralize} from '@wandb/weave/core/util/string';
import classNames from 'classnames';
import React, {useMemo, useRef, useState} from 'react';

import {buildCompositeMetricsMap} from '../../compositeMetricsUtil';
import {
  BOX_RADIUS,
  PLOT_HEIGHT,
  PLOT_PADDING,
  STANDARD_BORDER,
  STANDARD_PADDING,
} from '../../ecpConstants';
import {getOrderedCallIds} from '../../ecpState';
import {EvaluationComparisonState} from '../../ecpState';
import {
  flattenedDimensionPath,
  resolveSummaryMetricValueForEvaluateCall,
} from '../../ecpUtil';
import {HorizontalBox, VerticalBox} from '../../Layout';
import {PlotlyBarPlot} from './PlotlyBarPlot';
import {PlotlyRadarPlot, RadarPlotData} from './PlotlyRadarPlot';

/**
 * Summary plots produce plots to summarize evaluation comparisons.
 */
export const SummaryPlots: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const {radarData, allMetricNames} = useNormalizedPlotDataFromMetrics(
    props.state
  );
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>(
    Array.from(allMetricNames)
  );

  // filter down the plotlyRadarData to only include the selected metrics, after
  // computation, to allow quick addition/removal of metrics
  const filteredPlotlyRadarData = useMemo(() => {
    const filteredData: RadarPlotData = {};
    for (const [callId, metricBin] of Object.entries(radarData)) {
      const metrics: {[metric: string]: number} = {};
      for (const [metric, value] of Object.entries(metricBin.metrics)) {
        if (selectedMetrics.includes(metric)) {
          metrics[metric] = value;
        }
      }
      if (Object.keys(metrics).length > 0) {
        filteredData[callId] = {
          metrics: metrics,
          name: metricBin.name,
          color: metricBin.color,
        };
      }
    }
    return filteredData;
  }, [radarData, selectedMetrics]);

  return (
    <VerticalBox
      sx={{
        paddingLeft: STANDARD_PADDING,
        paddingRight: STANDARD_PADDING,
        flex: '1 1 auto',
        width: '100%',
      }}>
      <HorizontalBox
        sx={{
          width: '100%',
          alignItems: 'center',
          justifyContent: 'flex-start',
        }}>
        <Box
          sx={{
            fontSize: '1.5em',
            fontWeight: 'bold',
          }}>
          Summary Metrics
        </Box>
        <Box sx={{marginLeft: 'auto'}}>
          <div style={{display: 'flex', alignItems: 'center'}}>
            <div style={{marginRight: '4px'}}>Configure displayed metrics</div>
            <MetricsSelector
              setSelectedMetrics={setSelectedMetrics}
              selectedMetrics={selectedMetrics}
              allMetrics={Array.from(allMetricNames)}
            />
          </div>
        </Box>
      </HorizontalBox>
      <HorizontalBox
        sx={{
          flexWrap: 'wrap',
        }}>
        <Box
          sx={{
            flex: '1 2 ' + PLOT_HEIGHT + 'px',
            height: PLOT_HEIGHT,
            borderRadius: BOX_RADIUS,
            border: STANDARD_BORDER,
            overflow: 'hidden',
            alignContent: 'center',
            width: PLOT_HEIGHT,
          }}>
          <PlotlyRadarPlot
            height={PLOT_HEIGHT}
            data={filteredPlotlyRadarData}
          />
        </Box>
        <Box
          sx={{
            flex: '2 1 ' + PLOT_HEIGHT + 'px',
            height: PLOT_HEIGHT,
            overflow: 'hidden',
            borderRadius: BOX_RADIUS,
            border: STANDARD_BORDER,
            padding: PLOT_PADDING,
            width: PLOT_HEIGHT,
          }}>
          <PlotlyBarPlot height={PLOT_HEIGHT} data={filteredPlotlyRadarData} />
        </Box>
      </HorizontalBox>
    </VerticalBox>
  );
};

const MetricsSelector: React.FC<{
  setSelectedMetrics: (metrics: string[]) => void;
  selectedMetrics: string[];
  allMetrics: string[];
}> = ({setSelectedMetrics, selectedMetrics, allMetrics}) => {
  const [search, setSearch] = useState('');

  const ref = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const onClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : ref.current);
    setSearch('');
  };
  const open = Boolean(anchorEl);
  const id = open ? 'simple-popper' : undefined;

  const filteredCols = search
    ? allMetrics.filter(col => col.toLowerCase().includes(search.toLowerCase()))
    : allMetrics;

  const numHidden = allMetrics.length - selectedMetrics.length;
  const buttonSuffix = search ? `(${filteredCols.length})` : 'all';

  return (
    <>
      <span ref={ref}>
        <Button
          variant="ghost"
          icon="column"
          tooltip="Manage metrics"
          onClick={onClick}
        />
      </span>
      <Popover
        id={id}
        open={open}
        anchorEl={anchorEl}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'center',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'center',
        }}
        slotProps={{
          paper: {
            sx: {
              overflow: 'visible',
            },
          },
        }}
        onClose={() => setAnchorEl(null)}
        TransitionComponent={DraggableGrow}>
        <Tailwind>
          <div className="min-w-[360px] p-12">
            <DraggableHandle>
              <div className="flex items-center pb-8">
                <div className="flex-auto text-xl font-semibold">
                  Manage metrics
                </div>
                <div className="ml-16 text-moon-500">
                  {maybePluralize(numHidden, 'hidden column', 's')}
                </div>
              </div>
            </DraggableHandle>
            <div className="mb-8">
              <TextField
                placeholder="Filter columns"
                autoFocus
                value={search}
                onChange={setSearch}
              />
            </div>
            <div className="max-h-[300px] overflow-auto">
              {Array.from(allMetrics).map((metric: string) => {
                const value = metric;
                const idSwitch = `toggle-vis_${value}`;
                const checked = selectedMetrics.includes(metric);
                const label = metric;
                const disabled = false;
                if (
                  search &&
                  !label.toLowerCase().includes(search.toLowerCase())
                ) {
                  return null;
                }
                return (
                  <div key={value}>
                    <div
                      className={classNames(
                        'flex items-center py-2',
                        disabled ? 'opacity-40' : ''
                      )}>
                      <Switch.Root
                        id={idSwitch}
                        size="small"
                        checked={checked}
                        onCheckedChange={isOn => {
                          setSelectedMetrics(
                            isOn
                              ? [...selectedMetrics, metric]
                              : selectedMetrics.filter(m => m !== metric)
                          );
                        }}
                        disabled={disabled}>
                        <Switch.Thumb size="small" checked={checked} />
                      </Switch.Root>
                      <label
                        htmlFor={idSwitch}
                        className={classNames(
                          'ml-6',
                          disabled ? '' : 'cursor-pointer'
                        )}>
                        {label}
                      </label>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="mt-8 flex items-center">
              <Button
                size="small"
                variant="quiet"
                icon="hide-hidden"
                disabled={filteredCols.length === 0}
                onClick={() =>
                  setSelectedMetrics(
                    selectedMetrics.filter(m => !filteredCols.includes(m))
                  )
                }>
                {`Hide ${buttonSuffix}`}
              </Button>
              <div className="flex-auto" />
              <Button
                size="small"
                variant="quiet"
                icon="show-visible"
                disabled={filteredCols.length === 0}
                onClick={() =>
                  setSelectedMetrics(
                    Array.from(new Set([...selectedMetrics, ...filteredCols]))
                  )
                }>
                {`Show ${buttonSuffix}`}
              </Button>
            </div>
          </div>
        </Tailwind>
      </Popover>
    </>
  );
};

const normalizeValues = (values: Array<number | undefined>): number[] => {
  // find the max value
  // find the power of 2 that is greater than the max value
  // divide all values by that power of 2
  const maxVal = Math.max(...(values.filter(v => v !== undefined) as number[]));
  const maxPower = Math.ceil(Math.log2(maxVal));
  return values.map(val => (val ? val / 2 ** maxPower : 0));
};

const useNormalizedPlotDataFromMetrics = (
  state: EvaluationComparisonState
): {radarData: RadarPlotData; allMetricNames: Set<string>} => {
  const compositeMetrics = useMemo(() => {
    return buildCompositeMetricsMap(state.data, 'summary');
  }, [state]);
  const callIds = useMemo(() => {
    return getOrderedCallIds(state);
  }, [state]);

  return useMemo(() => {
    const normalizedMetrics = Object.values(compositeMetrics)
      .map(scoreGroup => Object.values(scoreGroup.metrics))
      .flat()
      .map(metric => {
        const values = callIds.map(callId => {
          const metricDimension = Object.values(metric.scorerRefs).find(
            scorerRefData => scorerRefData.evalCallIds.includes(callId)
          )?.metric;
          if (!metricDimension) {
            return undefined;
          }
          const val = resolveSummaryMetricValueForEvaluateCall(
            metricDimension,
            state.data.evaluationCalls[callId]
          );
          if (typeof val === 'boolean') {
            return val ? 1 : 0;
          } else {
            return val;
          }
        });
        const normalizedValues = normalizeValues(values);
        const evalScores: {[evalCallId: string]: number | undefined} =
          Object.fromEntries(
            callIds.map((key, i) => [key, normalizedValues[i]])
          );

        const metricLabel = flattenedDimensionPath(
          Object.values(metric.scorerRefs)[0].metric
        );
        return {
          metricLabel,
          evalScores,
        };
      });
    const radarData = Object.fromEntries(
      callIds.map(callId => {
        const evalCall = state.data.evaluationCalls[callId];
        return [
          evalCall.callId,
          {
            name: evalCall.name,
            color: evalCall.color,
            metrics: Object.fromEntries(
              normalizedMetrics.map(metric => {
                return [
                  metric.metricLabel,
                  metric.evalScores[evalCall.callId] ?? 0,
                ];
              })
            ),
          },
        ];
      })
    );
    const allMetricNames = new Set(normalizedMetrics.map(m => m.metricLabel));
    return {radarData, allMetricNames};
  }, [callIds, compositeMetrics, state.data.evaluationCalls]);
};
