/*
  ChartTypeSelectionDrawer.tsx

  This file contains the ChartTypeSelectionDrawer component, which displays a drawer containing
  buttons for the different chart types. Clicking a button will close the drawer and open a configuration
  modal for the selected chart type. The new chart will be added to the charts section.
*/
import {alpha, Box} from '@mui/material';
import {
  BLUE_300,
  BLUE_600,
  MOON_100,
  MOON_500,
} from '@wandb/weave/common/css/color.styles';
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
      title: 'Scatter plot',
      description:
        'Explore relationships between call metrics like latency vs cost.',
      icon: 'chart-scatterplot' as const,
    },
    {
      type: 'line' as const,
      title: 'Line chart',
      description: 'Track metrics over time with aggregated data points.',
      icon: 'line-plot-alt2' as const,
    },
    {
      type: 'bar' as const,
      title: 'Bar chart',
      description: 'Compare aggregated metrics across time bins.',
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
        Add chart
      </Box>
      <Button onClick={onClose} variant="ghost" icon="close" tooltip="Close" />
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
          py: 2,
          px: 2,
          display: 'flex',
          flexDirection: 'column',
          gap: 1,
        }}>
        <Box
          sx={{
            fontWeight: 600,
            fontSize: '14px',
            color: MOON_500,
            letterSpacing: '0.02em',
            textTransform: 'uppercase',
          }}>
          Charts
        </Box>
        {chartTypes.map(({type, title, description, icon}) => (
          <Box
            key={type}
            onClick={() => onSelectType(type)}
            sx={{
              marginLeft: '-8px',
              marginRight: '-8px',
              padding: '8px 8px',
              cursor: 'pointer',
              borderRadius: '8px',
              '&:hover': {
                backgroundColor: MOON_100,
              },
            }}>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                width: '100%',
              }}>
              <Box
                sx={{
                  backgroundColor: alpha(BLUE_300, 0.48),
                  minWidth: '40px',
                  minHeight: '40px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: '100px',
                }}>
                <Icon name={icon} color={BLUE_600} />
              </Box>
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
                    color: MOON_500,
                    width: '100%',
                    fontWeight: 400,
                  }}>
                  {description}
                </Box>
              </Box>
            </Box>
          </Box>
        ))}
      </Box>
    </ResizableDrawer>
  );
};
