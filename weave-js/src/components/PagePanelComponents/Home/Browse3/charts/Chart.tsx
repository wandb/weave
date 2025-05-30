import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import React from 'react';

import {Button} from '../../../../../components/Button';
import {chartContentStyle, chartLegendStyle, COLOR_PALETTE} from './chartUtils';
import {AggregationMethod} from './chartUtils';
import {ExtractedCallData, getOpNameDisplay, yAxisFields} from './extractData';
import {LegendChips} from './LegendChips';
import {LinePlot} from './LinePlot';
import {ScatterPlot} from './ScatterPlot';

export type ChartProps = {
  data: ExtractedCallData[];
  height?: number;
  xAxis?: string;
  yAxis?: string;
  plotType: 'scatter' | 'line';
  binCount?: number;
  aggregation?: AggregationMethod;
  groupKey?: string;
  title?: string;
  onEdit?: () => void;
  onRemove?: () => void;
  className?: string;
};

/**
 * Chart component that wraps LinePlot and ScatterPlot components with local hover state
 */
export const Chart: React.FC<ChartProps> = ({
  data,
  height,
  xAxis = 'started_at',
  yAxis = 'latency',
  plotType,
  binCount = 20,
  aggregation = 'average',
  groupKey,
  title,
  onEdit,
  onRemove,
  className,
}) => {
  // Local hover state for this chart instance
  const [hoveredGroup, setHoveredGroup] = React.useState<string | null>(null);

  // Get the y-axis field to access its units
  const yField = React.useMemo(() => {
    return yAxisFields.find(f => f.key === yAxis);
  }, [yAxis]);

  // Format the title with units if available
  const formattedTitle = React.useMemo(() => {
    if (!title) return '';
    if (!yField?.units) return title;
    return `${title} (${yField.units})`;
  }, [title, yField?.units]);

  // Local implementation of the legend chip hover handler
  const handleChipHover = React.useCallback((group: string | null) => {
    setHoveredGroup(group);
  }, []);

  // Calculate what plot to render
  const PlotComponent = plotType === 'line' ? LinePlot : ScatterPlot;

  // Get props for the plot component
  const plotProps = {
    data,
    height,
    initialXAxis: xAxis,
    initialYAxis: yAxis,
    hoveredGroup, // Pass the local hover state
    groupKey,
    ...(plotType === 'line' ? {binCount, aggregation} : {}),
  };

  // Get group values for the legend
  const groupValues = React.useMemo(() => {
    if (!groupKey || !data.length) return [];

    const values = new Set<string>();
    data.forEach(item => {
      if (typeof item[groupKey as keyof ExtractedCallData] === 'string') {
        const value = getOpNameDisplay(
          item[groupKey as keyof ExtractedCallData] as string
        );
        if (value) {
          values.add(value);
        }
      }
    });

    return Array.from(values);
  }, [data, groupKey]);

  // Function to create color mapping for groups
  const groupColor = React.useCallback(
    (group: string) => {
      const idx = groupValues.indexOf(group);
      return COLOR_PALETTE[idx % COLOR_PALETTE.length];
    },
    [groupValues]
  );

  return (
    <div
      className={className}
      style={{
        border: '1px solid #e0e0e0',
        borderRadius: 6,
        background: '#fff',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        minHeight: 0,
        boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
        overflow: 'hidden',
      }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '4px 8px',
          fontWeight: 500,
          userSelect: 'none',
          position: 'relative',
          height: 32,
          flex: '0 0 auto',
          borderBottom: '1px solid #e0e0e0',
        }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            minWidth: 0,
            flex: '0 0 auto',
          }}>
          <div
            className="drag-handle"
            style={{
              display: 'flex',
              alignItems: 'center',
              cursor: 'move',
              marginRight: 4,
            }}>
            <DragIndicatorIcon fontSize="small" style={{color: '#bdbdbd'}} />
          </div>
        </div>
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: 0,
            bottom: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            pointerEvents: 'none',
            zIndex: 0,
          }}>
          <span
            style={{
              fontWeight: 600,
              fontSize: 13,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              pointerEvents: 'none',
              color: '#666',
            }}>
            {formattedTitle}
          </span>
        </div>
        <div
          style={{
            display: 'flex',
            gap: 2,
            flex: '0 0 auto',
            zIndex: 1,
          }}>
          {onEdit && (
            <Button
              icon="settings"
              variant="ghost"
              size="small"
              onClick={onEdit}
            />
          )}
          {onRemove && (
            <Button
              icon="close"
              variant="ghost"
              size="small"
              onClick={onRemove}
            />
          )}
        </div>
      </div>
      <div
        style={{
          flex: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
        }}>
        {groupKey && groupValues.length > 0 && (
          <div
            style={chartLegendStyle}
            onMouseEnter={e => {
              e.currentTarget.style.overflow = 'auto';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.overflow = 'hidden';
            }}>
            <LegendChips
              groupValues={groupValues}
              groupColor={groupColor}
              onHover={handleChipHover}
              hoveredGroup={hoveredGroup}
            />
          </div>
        )}
        <div style={chartContentStyle}>
          <PlotComponent {...plotProps} />
        </div>
      </div>
    </div>
  );
};
