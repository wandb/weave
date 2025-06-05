import {Box} from '@mui/material';
import React from 'react';

import NumberInput from '../../../../../../common/components/elements/NumberInput';
import {Button} from '../../../../../../components/Button';
import {Select as CustomSelect} from '../../../../../../components/Form/Select';
import {Icon} from '../../../../../../components/Icon';
import {ResizableDrawer} from '../../pages/common/ResizableDrawer';
import {BarChart} from '../BarChart';
import {useMultipleOperations} from '../chartDataProcessing';
import {ChartConfig} from '../ChartsContext';
import {
  chartAxisFields,
  convertSchemaToAxisFields,
  extractInputOutputSchemaFromExtractedData,
  scatterXAxisFields,
  scatterYAxisFields,
  xAxisFields,
  yAxisFields,
} from '../extractData';
import {LinePlot} from '../LinePlot';
import {ScatterPlot} from '../ScatterPlot';
import {SectionHeader} from './SectionHeader';

interface ChartDrawerProps {
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
  filterFn?: (field: any) => boolean
): GroupedFieldOptions[] => {
  const groups: GroupedFieldOptions[] = [];

  // General section - base chart fields
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

export const ChartDrawer: React.FC<ChartDrawerProps> = ({
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

  const isScatterPlot = localConfig.plotType === 'scatter';

  // Create grouped options for each axis type
  const xAxisGroupedOptions = React.useMemo(() => {
    const baseFields = isScatterPlot ? scatterXAxisFields : xAxisFields;
    const filterFn = isScatterPlot
      ? undefined
      : (field: any) => field.type === 'number' || field.key === 'started_at';
    return createGroupedAxisOptions(baseFields, callData, filterFn);
  }, [isScatterPlot, callData]);

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

    // General section - base chart fields that are string/boolean
    const generalColorFields = chartAxisFields
      .filter(field => field.type === 'string' || field.type === 'boolean')
      .map(field => ({
        value: field.key,
        label: field.label,
      }));

    if (generalColorFields.length > 0) {
      groups.push({
        label: 'General',
        options: generalColorFields,
      });
    }

    // Input/Output sections
    if (callData.length > 0) {
      const schema = extractInputOutputSchemaFromExtractedData(callData);
      const inputOutputFields = convertSchemaToAxisFields(schema);

      // Filter to only include string and boolean fields for color grouping
      const colorGroupFields = inputOutputFields.filter(
        field => field.type === 'string' || field.type === 'boolean'
      );

      // Separate input and output fields
      const inputFields = colorGroupFields
        .filter(field => field.key.startsWith('input.'))
        .map(field => ({
          value: field.key,
          label: field.label.replace('Input: ', ''),
        }));

      const outputFields = colorGroupFields
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

  const drawerHeader = (
    <Box
      sx={{
        position: 'sticky',
        top: 0,
        zIndex: 20,
        pl: '16px',
        pr: '8px',
        height: 44,
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
          height: 44,
          display: 'flex',
          alignItems: 'center',
          fontWeight: 600,
          fontSize: '1.25rem',
        }}>
        Chart Settings
      </Box>
    </Box>
  );

  return (
    <ResizableDrawer
      open={open}
      onClose={onClose}
      headerContent={drawerHeader}
      defaultWidth={340}
      marginTop={60}>
      <Box
        pt={0}
        sx={{
          height: '100%',
          width: '100%',
          display: 'flex',
          flexDirection: 'column',
          p: 0,
        }}>
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            padding: 16,
          }}>
          <SectionHeader first>Chart</SectionHeader>
          <div style={{height: 220, margin: '16px 0'}}>
            {localConfig.plotType === 'line' ? (
              <LinePlot
                data={callData}
                height={320}
                initialYAxis={localConfig.yAxis}
                binCount={localConfig.binCount}
                aggregation={localConfig.aggregation}
                colorGroupKey={localConfig.colorGroupKey}
                groupKey={hasMultipleOperations ? 'op_name' : undefined}
              />
            ) : localConfig.plotType === 'bar' ? (
              <BarChart
                data={callData}
                height={320}
                initialYAxis={localConfig.yAxis}
                binCount={localConfig.binCount}
                aggregation={localConfig.aggregation}
                colorGroupKey={localConfig.colorGroupKey}
                groupKey={hasMultipleOperations ? 'op_name' : undefined}
              />
            ) : (
              <ScatterPlot
                data={callData}
                height={320}
                initialXAxis={localConfig.xAxis}
                initialYAxis={localConfig.yAxis}
                colorGroupKey={localConfig.colorGroupKey}
                groupKey={hasMultipleOperations ? 'op_name' : undefined}
                entity={entity}
                project={project}
              />
            )}
          </div>
          <SectionHeader>Plot Type</SectionHeader>
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
            localConfig.plotType === 'bar') && (
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
                    opt => opt.value === (localConfig.aggregation || 'average')
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
        </div>
        <Button
          onClick={() => onConfirm(localConfig)}
          style={{width: '100%', margin: 8}}
          variant="primary"
          size="large">
          {mode === 'edit' ? 'Confirm' : 'Create'}
        </Button>
      </Box>
    </ResizableDrawer>
  );
};
