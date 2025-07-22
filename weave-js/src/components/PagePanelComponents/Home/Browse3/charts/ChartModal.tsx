/*
  ChartModal.tsx

  This file contains the ChartModal component, which is used to display the chart and
  its configuration options when a new chart is created or an existing chart is edited.
*/
import {Box, Dialog, DialogContent, IconButton} from '@mui/material';
import {MOON_50} from '@wandb/weave/common/css/color.styles';
import React from 'react';

import NumberInput from '../../../../../common/components/elements/NumberInput';
import {Button} from '../../../../Button';
import {Select as CustomSelect} from '../../../../Form/Select';
import {TextField} from '../../../../Form/TextField';
import {Icon} from '../../../../Icon';
import {BarChart} from './BarChart';
import {generateChartAutoName} from './Chart';
import {useMultipleOperations} from './chartDataProcessing';
import {
  convertSchemaToAxisFields,
  extractDynamicFields,
  getCategoricalGroupingFields,
  scatterXAxisFields,
  scatterYAxisFields,
  xAxisFields,
  yAxisFields,
} from './extractData';
import {LinePlot} from './LinePlot';
import {ScatterPlot} from './ScatterPlot';
import {
  AggregationMethod,
  ChartAxisField,
  ChartConfig,
  ExtractedCallData,
} from './types';

export const SectionHeader: React.FC<{
  children: React.ReactNode;
  first?: boolean;
}> = ({children, first = false}) => (
  <div
    style={{
      textTransform: 'uppercase',
      fontSize: 12,
      color: '#888',
      fontWeight: 600,
      margin: `${first ? '0' : '12px'} 0 4px 0`,
      letterSpacing: 1,
    }}>
    {children}
  </div>
);

interface ChartModalProps {
  open: boolean;
  mode: 'create' | 'edit';
  initialConfig: Partial<ChartConfig>;
  onClose: () => void;
  onConfirm: (config: Partial<ChartConfig>) => void;
  callData: ExtractedCallData[];
  entity?: string;
  project?: string;
}

type FieldOption = {
  value: string;
  label: string;
};

type GroupedFieldOptions = {
  label: string;
  options: FieldOption[];
};

// Helper function to create grouped options from various field sources
const createGroupedFieldOptions = (
  baseFields: ChartAxisField[] | undefined,
  callData: ExtractedCallData[],
  filterFn?: (field: ChartAxisField) => boolean,
  labelTransforms?: {
    input?: (label: string) => string;
    output?: (label: string) => string;
  }
): GroupedFieldOptions[] => {
  const groups: GroupedFieldOptions[] = [];

  // General section - base chart fields
  if (baseFields) {
    const generalFields = baseFields
      .filter(field => !filterFn || filterFn(field))
      .map(field => ({
        value: field.key,
        label: field.label,
      }));

    if (generalFields.length > 0) {
      groups.push({
        label: 'General',
        options: generalFields,
      });
    }
  }

  // Dynamic fields from call data
  if (callData.length > 0) {
    const dynamicFields = baseFields
      ? (() => {
          const schema = extractDynamicFields(callData);
          return convertSchemaToAxisFields(schema);
        })()
      : getCategoricalGroupingFields(callData);

    // Filter fields if needed
    const filteredFields = dynamicFields.filter(
      field => !filterFn || filterFn(field)
    );

    // Helper function to create field options with label transformation
    const createFieldOptions = (
      prefix: string,
      labelTransform?: (label: string) => string
    ) =>
      filteredFields
        .filter(field => field.key.startsWith(prefix))
        .map(field => ({
          value: field.key,
          label: labelTransform ? labelTransform(field.label) : field.label,
        }));

    // Define field categories with their transformations
    const categories = [
      {
        label: 'Inputs',
        prefix: 'input.',
        transform:
          labelTransforms?.input ||
          ((label: string) => label.replace('Input: ', '')),
      },
      {
        label: 'Outputs',
        prefix: 'output.',
        transform:
          labelTransforms?.output ||
          ((label: string) => label.replace('Output: ', '')),
      },
      {
        label: 'Annotations',
        prefix: 'annotations.',
      },
      {
        label: 'Scores',
        prefix: 'scores.',
      },
      {
        label: 'Reactions',
        prefix: 'reactions.',
      },
    ];

    // Add each category if it has fields
    categories.forEach(category => {
      const fields = createFieldOptions(category.prefix, category.transform);
      if (fields.length > 0) {
        groups.push({
          label: category.label,
          options: fields,
        });
      }
    });
  }

  return groups;
};

export const ChartModal: React.FC<ChartModalProps> = ({
  open,
  mode,
  initialConfig,
  onClose,
  onConfirm,
  callData,
  entity,
  project,
}) => {
  const [localConfig, setLocalConfig] =
    React.useState<Partial<ChartConfig>>(initialConfig);

  React.useEffect(() => {
    setLocalConfig(initialConfig);
  }, [initialConfig, open]);

  const hasMultipleOperations = useMultipleOperations(callData);

  // Determine effective groupKeys based on multiple operations and user selection
  const effectiveGroupKeys = React.useMemo(() => {
    const keys: string[] = [];

    // Always include op_name when there are multiple operations
    if (hasMultipleOperations) {
      keys.push('op_name');
    }

    // Add user-configured group keys (excluding op_name to avoid duplicates)
    if (localConfig.groupKeys) {
      localConfig.groupKeys.forEach(key => {
        if (key !== 'op_name' && !keys.includes(key)) {
          keys.push(key);
        }
      });
    }

    return keys.length > 0 ? keys : undefined;
  }, [hasMultipleOperations, localConfig.groupKeys]);

  const isScatterPlot = localConfig.plotType === 'scatter';
  const xAxisGroupedOptions = React.useMemo(() => {
    const baseFields = isScatterPlot ? scatterXAxisFields : xAxisFields;
    const filterFn = isScatterPlot
      ? undefined
      : (field: ChartAxisField) => field.key === 'started_at';
    return createGroupedFieldOptions(baseFields, callData, filterFn);
  }, [isScatterPlot, callData]);

  const yAxisGroupedOptions = React.useMemo(() => {
    const baseFields = isScatterPlot ? scatterYAxisFields : yAxisFields;
    const filterFn = (field: ChartAxisField) =>
      field.type === 'number' || field.type === 'boolean';
    return createGroupedFieldOptions(baseFields, callData, filterFn);
  }, [isScatterPlot, callData]);

  const plotTypeOptions = [
    {
      value: 'scatter',
      label: (
        <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
          <Icon name="chart-scatterplot" />
          Scatter plot
        </Box>
      ),
    },
    {
      value: 'line',
      label: (
        <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
          <Icon name="line-plot-alt2" />
          Line plot
        </Box>
      ),
    },
    {
      value: 'bar',
      label: (
        <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
          <Icon name="chart-vertical-bars" />
          Bar chart
        </Box>
      ),
    },
  ];

  const aggregationOptions: {value: AggregationMethod; label: string}[] = [
    {value: 'average', label: 'average'},
    {value: 'sum', label: 'sum'},
    {value: 'min', label: 'min'},
    {value: 'max', label: 'max'},
    {value: 'p95', label: 'p95'},
    {value: 'p99', label: 'p99'},
  ];

  // Generate grouping options for scatter plots, line plots, and bar charts
  const colorGroupGroupedOptions = React.useMemo((): GroupedFieldOptions[] => {
    if (
      !isScatterPlot &&
      localConfig.plotType !== 'line' &&
      localConfig.plotType !== 'bar'
    )
      return [];

    return createGroupedFieldOptions(undefined, callData);
  }, [isScatterPlot, localConfig.plotType, callData]);

  // Helper function to find selected option in grouped options
  const findSelectedOption = (
    groupedOptions: GroupedFieldOptions[],
    value?: string
  ) => {
    if (!value) return null;
    for (const group of groupedOptions) {
      const option = group.options.find(opt => opt.value === value);
      if (option) return option;
    }
    return null;
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth={false}
      fullWidth
      sx={{
        '& .MuiDialog-paper': {
          height: 'calc(95vh - 120px)',
          maxHeight: 'calc(95vh - 120px)',
          width: '95vw',
          maxWidth: '95vw',
          margin: '120px auto auto auto',
          borderRadius: '8px',
        },
      }}>
      <DialogContent
        sx={{
          p: 0,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
        }}>
        {/* Header */}
        <Box
          sx={{
            position: 'sticky',
            top: 0,
            zIndex: 20,
            pl: '24px',
            pr: '16px',
            height: 64,
            width: '100%',
            borderBottom: `1px solid #e0e0e0`,
            display: 'flex',
            flexDirection: 'row',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: 'white',
          }}>
          <Box
            sx={{
              height: 64,
              display: 'flex',
              alignItems: 'center',
              fontWeight: 600,
              fontSize: '1.25rem',
            }}>
            Chart settings
          </Box>
          <IconButton onClick={onClose} sx={{color: '#666'}}>
            <Icon name="close" />
          </IconButton>
        </Box>

        {/* Main Content */}
        <Box
          sx={{flex: 1, display: 'flex', flexDirection: 'row', minHeight: 0}}>
          {/* Chart Preview Section */}
          <Box
            sx={{
              flex: 1,
              minWidth: 0,
              p: 3,
              borderRight: '1px solid #e0e0e0',
              display: 'flex',
              flexDirection: 'column',
            }}>
            <SectionHeader first>Chart Preview</SectionHeader>
            <Box sx={{flex: 1, mt: 2, minHeight: 400}}>
              {localConfig.plotType === 'line' ? (
                <LinePlot
                  data={callData}
                  initialXAxis={localConfig.xAxis}
                  initialYAxis={localConfig.yAxis}
                  binCount={localConfig.binCount}
                  aggregation={localConfig.aggregation}
                  groupKeys={effectiveGroupKeys}
                  isFullscreen={true}
                />
              ) : localConfig.plotType === 'bar' ? (
                <BarChart
                  data={callData}
                  initialXAxis={localConfig.xAxis}
                  initialYAxis={localConfig.yAxis}
                  binCount={localConfig.binCount}
                  aggregation={localConfig.aggregation}
                  groupKeys={effectiveGroupKeys}
                  isFullscreen={true}
                />
              ) : (
                <ScatterPlot
                  data={callData}
                  initialXAxis={localConfig.xAxis}
                  initialYAxis={localConfig.yAxis}
                  groupKeys={effectiveGroupKeys}
                  entity={entity}
                  project={project}
                  isFullscreen={true}
                />
              )}
            </Box>
          </Box>

          {/* Controls Section */}
          <Box
            sx={{
              width: 320,
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              p: 3,
              backgroundColor: MOON_50,
            }}>
            <SectionHeader first>Chart Name</SectionHeader>
            <Box sx={{mb: 2}}>
              <TextField
                value={localConfig.customName || ''}
                onChange={value =>
                  setLocalConfig(prev => ({
                    ...prev,
                    customName: value || undefined,
                  }))
                }
                placeholder={
                  localConfig.yAxis &&
                  localConfig.plotType &&
                  localConfig.aggregation
                    ? generateChartAutoName(
                        localConfig.yAxis,
                        localConfig.plotType,
                        localConfig.aggregation,
                        localConfig.xAxis || 'started_at',
                        callData
                      )
                    : 'Chart name'
                }
                variant="default"
                size="medium"
              />
            </Box>

            <SectionHeader>Plot Type</SectionHeader>
            <CustomSelect
              value={
                plotTypeOptions.find(
                  opt => opt.value === (localConfig.plotType || 'scatter')
                ) || plotTypeOptions[0]
              }
              onChange={option => {
                const newPlotType = (option ? option.value : 'scatter') as
                  | 'scatter'
                  | 'line'
                  | 'bar';

                setLocalConfig(prev => ({
                  ...prev,
                  plotType: newPlotType,
                  // Auto-set xAxis to 'started_at' for bar and line charts
                  xAxis:
                    newPlotType === 'bar' || newPlotType === 'line'
                      ? 'started_at'
                      : prev.xAxis,
                }));
              }}
              options={plotTypeOptions}
              size="medium"
            />

            <SectionHeader>Y-Axis</SectionHeader>
            <CustomSelect
              value={findSelectedOption(yAxisGroupedOptions, localConfig.yAxis)}
              onChange={option =>
                setLocalConfig(prev => ({
                  ...prev,
                  yAxis: option ? option.value : '',
                }))
              }
              options={yAxisGroupedOptions}
              size="medium"
              groupDivider={true}
            />

            {localConfig.plotType === 'scatter' && (
              <>
                <SectionHeader>X-Axis</SectionHeader>
                <CustomSelect
                  value={findSelectedOption(
                    xAxisGroupedOptions,
                    localConfig.xAxis
                  )}
                  onChange={option =>
                    setLocalConfig(prev => ({
                      ...prev,
                      xAxis: option ? option.value : '',
                    }))
                  }
                  options={xAxisGroupedOptions}
                  size="medium"
                  groupDivider={true}
                />
              </>
            )}

            {(localConfig.plotType === 'line' ||
              localConfig.plotType === 'bar') && (
              <>
                <SectionHeader>X-Axis</SectionHeader>
                <CustomSelect
                  value={findSelectedOption(
                    xAxisGroupedOptions,
                    localConfig.xAxis
                  )}
                  onChange={option =>
                    setLocalConfig(prev => ({
                      ...prev,
                      xAxis: option ? option.value : '',
                    }))
                  }
                  options={xAxisGroupedOptions}
                  size="medium"
                  groupDivider={true}
                  isDisabled={true}
                />
              </>
            )}

            {(localConfig.plotType === 'scatter' ||
              localConfig.plotType === 'line' ||
              localConfig.plotType === 'bar') && (
              <>
                <SectionHeader>Grouping</SectionHeader>
                <CustomSelect
                  value={findSelectedOption(
                    colorGroupGroupedOptions,
                    localConfig.groupKeys?.find(key => key !== 'op_name')
                  )}
                  onChange={option => {
                    const newGroupKeys: string[] = [];

                    // Always include op_name when there are multiple operations
                    if (hasMultipleOperations) {
                      newGroupKeys.push('op_name');
                    }

                    // Add user-selected key if provided
                    if (option && option.value !== 'op_name') {
                      newGroupKeys.push(option.value);
                    }

                    setLocalConfig(prev => ({
                      ...prev,
                      groupKeys:
                        newGroupKeys.length > 0 ? newGroupKeys : undefined,
                    }));
                  }}
                  options={colorGroupGroupedOptions}
                  size="medium"
                  placeholder="No grouping"
                  groupDivider={true}
                  isClearable={true}
                />
              </>
            )}

            {!isScatterPlot && (
              <>
                <SectionHeader>Binning</SectionHeader>
                <NumberInput
                  min={1}
                  max={200}
                  value={localConfig.binCount ?? 20}
                  onChange={val =>
                    setLocalConfig(prev => ({
                      ...prev,
                      binCount: val ?? 20,
                    }))
                  }
                  stepper
                  useStepperPlusMinus
                  containerStyle={{}}
                />

                <SectionHeader>Aggregation</SectionHeader>
                <CustomSelect
                  value={
                    aggregationOptions.find(
                      opt =>
                        opt.value === (localConfig.aggregation || 'average')
                    ) || aggregationOptions[0]
                  }
                  onChange={option =>
                    setLocalConfig(prev => ({
                      ...prev,
                      aggregation: option
                        ? (option.value as ChartConfig['aggregation'])
                        : 'average',
                    }))
                  }
                  options={aggregationOptions}
                  size="medium"
                />
              </>
            )}
          </Box>
        </Box>

        {/* Footer */}
        <Box
          sx={{
            borderTop: '1px solid #e0e0e0',
            backgroundColor: MOON_50,
            py: 1.5,
            px: 2,
            display: 'flex',
            justifyContent: 'flex-end',
            gap: 2,
          }}>
          <Button onClick={onClose} variant="secondary" size="large">
            Cancel
          </Button>
          <Button
            onClick={() => onConfirm(localConfig)}
            variant="primary"
            size="large">
            Save chart
          </Button>
        </Box>
      </DialogContent>
    </Dialog>
  );
};
