import {Box, Dialog, DialogContent, IconButton} from '@mui/material';
import React from 'react';

import NumberInput from '../../../../../common/components/elements/NumberInput';
import {Button} from '../../../../Button';
import {Select as CustomSelect} from '../../../../Form/Select';
import {Icon} from '../../../../Icon';
import {BarChart} from './BarChart';
import {useMultipleOperations} from './chartDataProcessing';
import {useChartsState} from './ChartsContext';
import {
  chartAxisFields,
  convertSchemaToAxisFields,
  extractInputOutputSchemaFromExtractedData,
  getCategoricalGroupingFields,
  scatterXAxisFields,
  scatterYAxisFields,
  xAxisFields,
  yAxisFields,
} from './extractData';
import {LinePlot} from './LinePlot';
import {ScatterPlot} from './ScatterPlot';
import {ChartConfig} from './types';

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
  callData: any[];
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

// Helper function to create grouped options
const createGroupedAxisOptions = (
  baseFields: typeof chartAxisFields,
  callData: any[],
  filterFn?: (field: any) => boolean,
  isEvalContext?: boolean,
  isXAxisForNonScatter?: boolean
): GroupedFieldOptions[] => {
  const groups: GroupedFieldOptions[] = [];

  // General section - base chart fields
  let generalFields = baseFields
    .filter(field => !filterFn || filterFn(field))
    .map(field => ({
      value: field.key,
      label: field.label,
    }));

  // Add prediction index for eval context on line/bar charts x-axis
  if (isEvalContext && isXAxisForNonScatter) {
    generalFields = generalFields.filter(
      field => field.value !== 'prediction_index'
    );
    generalFields.unshift({
      value: 'prediction_index',
      label: 'Prediction Index',
    });
  } else {
    // Remove prediction index from options when not in eval context or not for x-axis of line/bar
    generalFields = generalFields.filter(
      field => field.value !== 'prediction_index'
    );
  }

  if (generalFields.length > 0) {
    groups.push({
      label: 'General',
      options: generalFields,
    });
  }

  // Input/Output sections
  if (callData.length > 0) {
    const schema = extractInputOutputSchemaFromExtractedData(callData);
    const inputOutputFields = convertSchemaToAxisFields(schema);

    // Filter fields if needed
    const filteredFields = inputOutputFields.filter(
      field => !filterFn || filterFn(field)
    );

    // Separate input and output fields
    const inputFields = filteredFields
      .filter(field => field.key.startsWith('input.'))
      .map(field => ({
        value: field.key,
        label: field.label.replace('Input: ', ''),
      }));

    const outputFields = filteredFields
      .filter(field => field.key.startsWith('output.'))
      .map(field => ({
        value: field.key,
        label: field.label.replace('Output: ', ''),
      }));

    if (inputFields.length > 0) {
      groups.push({
        label: 'Inputs',
        options: inputFields,
      });
    }

    if (outputFields.length > 0) {
      groups.push({
        label: 'Outputs',
        options: outputFields,
      });
    }
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
  const {pageType} = useChartsState();
  const [localConfig, setLocalConfig] =
    React.useState<Partial<ChartConfig>>(initialConfig);

  React.useEffect(() => {
    setLocalConfig(initialConfig);
  }, [initialConfig, open]);

  const isScatterPlot = localConfig.plotType === 'scatter';
  const isEvalContext = pageType === 'evaluations';
  const isPredictionIndexSelected = localConfig.xAxis === 'prediction_index';
  const shouldHideBinningAggregation =
    isPredictionIndexSelected &&
    (localConfig.plotType === 'line' || localConfig.plotType === 'bar');

  // Create grouped options for each axis type
  const xAxisGroupedOptions = React.useMemo(() => {
    const baseFields = isScatterPlot ? scatterXAxisFields : xAxisFields;
    const filterFn = isScatterPlot
      ? undefined
      : (field: any) =>
          field.type === 'number' ||
          field.key === 'started_at' ||
          field.key === 'prediction_index';
    return createGroupedAxisOptions(
      baseFields,
      callData,
      filterFn,
      isEvalContext,
      !isScatterPlot
    );
  }, [isScatterPlot, callData, isEvalContext]);

  const yAxisGroupedOptions = React.useMemo(() => {
    const baseFields = isScatterPlot ? scatterYAxisFields : yAxisFields;
    const filterFn = (field: any) => field.type === 'number';
    return createGroupedAxisOptions(baseFields, callData, filterFn);
  }, [isScatterPlot, callData]);

  const plotTypeOptions = [
    {
      value: 'scatter',
      label: (
        <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
          <Icon name="chart-scatterplot" />
          Scatter Plot
        </Box>
      ),
    },
    {
      value: 'line',
      label: (
        <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
          <Icon name="line-plot-alt2" />
          Line Plot
        </Box>
      ),
    },
    {
      value: 'bar',
      label: (
        <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
          <Icon name="chart-vertical-bars" />
          Bar Chart
        </Box>
      ),
    },
  ];

  const aggregationOptions = [
    {value: 'average', label: 'Average'},
    {value: 'sum', label: 'Sum'},
    {value: 'min', label: 'Min'},
    {value: 'max', label: 'Max'},
    {value: 'p95', label: 'P95'},
    {value: 'p99', label: 'P99'},
  ];

  // Generate color grouping options for scatter plots, line plots, and bar charts
  const colorGroupGroupedOptions = React.useMemo((): GroupedFieldOptions[] => {
    if (
      !isScatterPlot &&
      localConfig.plotType !== 'line' &&
      localConfig.plotType !== 'bar'
    )
      return [];

    const groups: GroupedFieldOptions[] = [];

    // Get all categorical fields using the improved filtering logic
    const categoricalFields = getCategoricalGroupingFields(callData);

    // Separate into general, input, and output fields
    const generalFields = categoricalFields
      .filter(
        field =>
          !field.key.startsWith('input.') && !field.key.startsWith('output.')
      )
      .map(field => ({
        value: field.key,
        label: field.label,
      }));

    const inputFields = categoricalFields
      .filter(field => field.key.startsWith('input.'))
      .map(field => ({
        value: field.key,
        label: field.label.replace('Input: ', ''),
      }));

    const outputFields = categoricalFields
      .filter(field => field.key.startsWith('output.'))
      .map(field => ({
        value: field.key,
        label: field.label.replace('Output: ', ''),
      }));

    // Add groups if they have fields
    if (generalFields.length > 0) {
      groups.push({
        label: 'General',
        options: generalFields,
      });
    }

    if (inputFields.length > 0) {
      groups.push({
        label: 'Inputs',
        options: inputFields,
      });
    }

    if (outputFields.length > 0) {
      groups.push({
        label: 'Outputs',
        options: outputFields,
      });
    }

    return groups;
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

  const hasMultipleOperations = useMultipleOperations(callData);

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
              fontSize: '1.5rem',
            }}>
            Chart Settings
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
                  height={600}
                  initialXAxis={localConfig.xAxis}
                  initialYAxis={localConfig.yAxis}
                  binCount={localConfig.binCount}
                  aggregation={localConfig.aggregation}
                  colorGroupKey={localConfig.colorGroupKey}
                  groupKey={hasMultipleOperations ? 'op_name' : undefined}
                  isFullscreen={true}
                />
              ) : localConfig.plotType === 'bar' ? (
                <BarChart
                  data={callData}
                  height={600}
                  initialXAxis={localConfig.xAxis}
                  initialYAxis={localConfig.yAxis}
                  binCount={localConfig.binCount}
                  aggregation={localConfig.aggregation}
                  colorGroupKey={localConfig.colorGroupKey}
                  groupKey={hasMultipleOperations ? 'op_name' : undefined}
                  isFullscreen={true}
                />
              ) : (
                <ScatterPlot
                  data={callData}
                  height={600}
                  initialXAxis={localConfig.xAxis}
                  initialYAxis={localConfig.yAxis}
                  colorGroupKey={localConfig.colorGroupKey}
                  groupKey={hasMultipleOperations ? 'op_name' : undefined}
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
              backgroundColor: '#fafafa',
            }}>
            <SectionHeader first>Plot Type</SectionHeader>
            <CustomSelect
              value={
                plotTypeOptions.find(
                  opt => opt.value === (localConfig.plotType || 'scatter')
                ) || plotTypeOptions[0]
              }
              onChange={option =>
                setLocalConfig(prev => ({
                  ...prev,
                  plotType: (option ? option.value : 'scatter') as
                    | 'scatter'
                    | 'line'
                    | 'bar',
                }))
              }
              options={plotTypeOptions}
              size="small"
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
              size="small"
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
                  size="small"
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
                  size="small"
                  groupDivider={true}
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
                    localConfig.colorGroupKey
                  )}
                  onChange={option =>
                    setLocalConfig(prev => ({
                      ...prev,
                      colorGroupKey: option ? option.value : undefined,
                    }))
                  }
                  options={colorGroupGroupedOptions}
                  size="small"
                  placeholder="No color grouping"
                  groupDivider={true}
                  isClearable={true}
                />
              </>
            )}

            {(localConfig.plotType === 'line' ||
              localConfig.plotType === 'bar') &&
              !shouldHideBinningAggregation && (
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
                    size="small"
                  />
                </>
              )}
          </Box>
        </Box>

        {/* Footer */}
        <Box
          sx={{
            borderTop: '1px solid #e0e0e0',
            p: 3,
            display: 'flex',
            justifyContent: 'flex-end',
            gap: 2,
          }}>
          <Button onClick={onClose} variant="ghost" size="large">
            Cancel
          </Button>
          <Button
            onClick={() => onConfirm(localConfig)}
            variant="primary"
            size="large">
            Save Changes
          </Button>
        </Box>
      </DialogContent>
    </Dialog>
  );
};
