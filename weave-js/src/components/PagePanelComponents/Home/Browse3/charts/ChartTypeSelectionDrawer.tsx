/*
  ChartTypeSelectionDrawer.tsx

  This file contains the ChartTypeSelectionDrawer component, which displays a drawer containing
  buttons for the different chart types. Clicking a button will close the drawer and open a configuration
  modal for the selected chart type. The new chart will be added to the charts section.
*/
import {Box} from '@mui/material';
import React from 'react';

import {Button} from '../../../../Button';
import {Icon} from '../../../../Icon';
import {ResizableDrawer} from '../pages/common/ResizableDrawer';

interface ChartTypeSelectionDrawerProps {
  open: boolean;
  onClose: () => void;
  onSelectType: (plotType: 'scatter' | 'line' | 'bar') => void;
}

export const ChartTypeSelectionDrawer: React.FC<
  ChartTypeSelectionDrawerProps
> = ({open, onClose, onSelectType}) => {
  const chartTypes = [
    {
      type: 'scatter' as const,
      title: 'Scatter Plot',
      description:
        'Explore relationships between call metrics like latency vs cost',
      icon: 'chart-scatterplot' as const,
    },
    {
      type: 'line' as const,
      title: 'Line Chart',
      description: 'Track metrics over time with aggregated data points',
      icon: 'line-plot-alt2' as const,
    },
    {
      type: 'bar' as const,
      title: 'Bar Chart',
      description: 'Compare aggregated metrics across time bins',
      icon: 'chart-vertical-bars' as const,
    },
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
        Create chart
      </Box>
      <Button
        onClick={onClose}
        variant="ghost"
        icon="close"
        tooltip="Close"
      />
    </Box>
  );

  return (
    <ResizableDrawer
      open={open}
      onClose={onClose}
      headerContent={drawerHeader}
      defaultWidth={400}
      marginTop={60}>
      <Box
        sx={{
          p: 3,
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
        }}>
        {chartTypes.map(({type, title, description, icon}) => (
          <Button
            key={type}
            onClick={() => onSelectType(type)}
            variant="ghost"
            size="large"
            style={{
              justifyContent: 'flex-start',
              padding: '16px',
              height: 'auto',
              border: '1px solid #e0e0e0',
              borderRadius: '8px',
              width: '100%',
            }}>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 2,
                width: '100%',
              }}>
              <Icon name={icon} />
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                  textAlign: 'left',
                  width: '100%',
                }}>
                <Box
                  sx={{
                    fontWeight: 600,
                    fontSize: '16px',
                  }}>
                  {title}
                </Box>
                <Box
                  sx={{
                    fontSize: '14px',
                    color: '#666',
                    mt: 0.5,
                    width: '100%',
                  }}>
                  {description}
                </Box>
              </Box>
            </Box>
          </Button>
        ))}
      </Box>
    </ResizableDrawer>
  );
};
