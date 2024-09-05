import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Box, IconButton } from '@material-ui/core';
import { ChevronLeft, ChevronRight } from '@mui/icons-material';
import { RadarPlotData } from './PlotlyRadarPlot';
import { PlotlyBarPlot } from './PlotlyBarPlot';
import { BOX_RADIUS, STANDARD_BORDER } from '../../ecpConstants';

const PAGER_HEIGHT = 40;
const MIN_PLOT_WIDTH = 200; // Minimum width for a plot
const MIN_GAP = 16; // Minimum gap between plots

export const MultiPlotBarChart: React.FC<{
  height: number;
  data: RadarPlotData;
}> = ({ height, data }) => {
  const [currentPage, setCurrentPage] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const [plotsPerRow, setPlotsPerRow] = useState(3);
  const [plotWidth, setPlotWidth] = useState(MIN_PLOT_WIDTH);

  const metrics = useMemo(() => Object.keys(Object.values(data)[0].metrics), [data]);

  useEffect(() => {
    const updateLayout = () => {
      if (containerRef.current) {
        const containerWidth = containerRef.current.offsetWidth;
        const maxPlotsPerRow = Math.floor((containerWidth + MIN_GAP) / (MIN_PLOT_WIDTH + MIN_GAP));
        const optimalPlotsPerRow = Math.min(maxPlotsPerRow, metrics.length);
        const newPlotsPerRow = Math.max(1, optimalPlotsPerRow);
        setPlotsPerRow(newPlotsPerRow);

        // Calculate the new plot width to fill the available space
        const newPlotWidth = Math.max(
          MIN_PLOT_WIDTH,
          (containerWidth - (newPlotsPerRow - 1) * MIN_GAP) / newPlotsPerRow
        );
        setPlotWidth(newPlotWidth);
      }
    };

    updateLayout();
    window.addEventListener('resize', updateLayout);
    return () => window.removeEventListener('resize', updateLayout);
  }, [metrics.length]);

  const totalPages = Math.ceil(metrics.length / plotsPerRow);

  const currentMetrics = useMemo(() => {
    const start = currentPage * plotsPerRow;
    return metrics.slice(start, start + plotsPerRow);
  }, [currentPage, metrics, plotsPerRow]);

  const handlePrevious = () => {
    setCurrentPage(prev => (prev > 0 ? prev - 1 : totalPages - 1));
  };

  const handleNext = () => {
    setCurrentPage(prev => (prev < totalPages - 1 ? prev + 1 : 0));
  };

  const plotHeight = height - PAGER_HEIGHT;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }} ref={containerRef}>
      <Box sx={{ display: 'flex', justifyContent: 'flex-start', flex: 1, mb: 2 }}>
        {currentMetrics.map((metric, index) => (
          <Box 
            key={metric} 
            sx={{
              width: plotWidth,
              height: plotHeight,
              borderRadius: BOX_RADIUS,
              border: STANDARD_BORDER,
              overflow: 'hidden',
              marginLeft: index > 0 ? `${MIN_GAP}px` : 0, // Apply gap only between plots
            }}
          >
            <PlotlyBarPlot
              height={plotHeight}
              width={plotWidth}
              data={data}
              metric={metric}
            />
          </Box>
        ))}
      </Box>
      <Box sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'flex-end',
        height: PAGER_HEIGHT,
      }}>
        <IconButton onClick={handlePrevious} size="small">
          <ChevronLeft />
        </IconButton>
        <Box sx={{ mx: 2 }}>
          {currentPage + 1} / {totalPages}
        </Box>
        <IconButton onClick={handleNext} size="small">
          <ChevronRight />
        </IconButton>
      </Box>
    </Box>
  );
};