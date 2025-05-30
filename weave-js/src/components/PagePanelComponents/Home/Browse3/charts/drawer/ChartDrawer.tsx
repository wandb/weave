import {Box} from '@mui/material';
import React from 'react';

import NumberInput from '../../../../../../common/components/elements/NumberInput';
import {Button} from '../../../../../../components/Button';
import {Select as CustomSelect} from '../../../../../../components/Form/Select';
import {ResizableDrawer} from '../../pages/common/ResizableDrawer';
import {ChartConfig} from '../ChartsContext';
import {xAxisFields, yAxisFields} from '../extractData';
import {LinePlot} from '../LinePlot';
import {ScatterPlot} from '../ScatterPlot';
import {FieldLabel} from './FieldLabel';
import {SectionHeader} from './SectionHeader';

interface ChartDrawerProps {
  open: boolean;
  mode: 'create' | 'edit';
  initialConfig: Partial<ChartConfig>;
  onClose: () => void;
  onConfirm: (config: Partial<ChartConfig>) => void;
  callData: any[];
}

export const ChartDrawer: React.FC<ChartDrawerProps> = ({
  open,
  mode,
  initialConfig,
  onClose,
  onConfirm,
  callData,
}) => {
  const [localConfig, setLocalConfig] =
    React.useState<Partial<ChartConfig>>(initialConfig);
  React.useEffect(() => {
    setLocalConfig(initialConfig);
  }, [initialConfig, open]);

  const xAxisOptions = xAxisFields.map(f => ({
    value: f.key,
    label: f.label,
  }));
  const yAxisOptions = yAxisFields.map(f => ({
    value: f.key,
    label: f.label,
  }));
  const plotTypeOptions = [
    {value: 'scatter', label: 'Scatter Plot'},
    {value: 'line', label: 'Line Plot'},
  ];
  const aggregationOptions = [
    {value: 'average', label: 'Average'},
    {value: 'sum', label: 'Sum'},
    {value: 'min', label: 'Min'},
    {value: 'max', label: 'Max'},
    {value: 'p95', label: 'P95'},
    {value: 'p99', label: 'P99'},
  ];

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
                initialXAxis={localConfig.xAxis}
                initialYAxis={localConfig.yAxis}
                binCount={localConfig.binCount}
                aggregation={localConfig.aggregation}
                groupKey={localConfig.groupKey}
              />
            ) : (
              <ScatterPlot
                data={callData}
                height={320}
                initialXAxis={localConfig.xAxis}
                initialYAxis={localConfig.yAxis}
                groupKey={localConfig.groupKey}
              />
            )}
          </div>
          <FieldLabel>Plot Type</FieldLabel>
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
                  | 'line',
              }))
            }
            options={plotTypeOptions}
            size="small"
          />
          <SectionHeader>X-Axis</SectionHeader>
          <FieldLabel>Value</FieldLabel>
          <CustomSelect
            value={
              xAxisOptions.find(opt => opt.value === localConfig.xAxis) || null
            }
            onChange={option =>
              setLocalConfig(prev => ({
                ...prev,
                xAxis: option ? option.value : '',
              }))
            }
            options={xAxisOptions}
            size="small"
          />
          {localConfig.plotType === 'line' && (
            <>
              <FieldLabel>Bin Count</FieldLabel>
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
              <FieldLabel>Aggregation</FieldLabel>
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
          <SectionHeader>Y-Axis</SectionHeader>
          <FieldLabel>Value</FieldLabel>
          <CustomSelect
            value={
              yAxisOptions.find(opt => opt.value === localConfig.yAxis) || null
            }
            onChange={option =>
              setLocalConfig(prev => ({
                ...prev,
                yAxis: option ? option.value : '',
              }))
            }
            options={yAxisOptions}
            size="small"
          />
          <SectionHeader>Grouping</SectionHeader>
          <FieldLabel>Group By</FieldLabel>
          <CustomSelect
            value={{
              value: localConfig.groupKey || '',
              label:
                localConfig.groupKey === 'op_name' ? 'Operation Name' : 'None',
            }}
            onChange={option =>
              setLocalConfig(prev => ({
                ...prev,
                groupKey: option && option.value ? option.value : undefined,
              }))
            }
            options={[
              {value: '', label: 'None'},
              {value: 'op_name', label: 'Operation Name'},
            ]}
            size="small"
          />
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
