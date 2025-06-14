export const CHIP_HEIGHT = 18;

export const chartContainerStyle = {
  display: 'flex',
  flexDirection: 'column' as const,
  height: '100%',
  width: '100%',
  minHeight: 0,
  flex: 1,
};

export const chartLegendStyle = {
  maxHeight: CHIP_HEIGHT * 2 + 12,
  marginBottom: 8,
  overflow: 'hidden',
  paddingRight: 10,
  flex: '0 0 auto' as const,
};

export const chartContentStyle = {
  flex: 1,
  minHeight: 0,
  display: 'flex' as const,
  flexDirection: 'column' as const,
  width: '100%',
  position: 'relative' as const,
  justifyContent: 'flex-start' as const,
  alignItems: 'flex-start' as const,
};

export const chartTooltipStyle = {
  cursor: {
    stroke: '#999',
    strokeWidth: 1,
    strokeDasharray: '5 5',
  },
  isAnimationActive: false,
};

export const tooltipContainerStyle = (isFullscreen?: boolean) => ({
  backgroundColor: 'rgba(255, 255, 255, 0.95)',
  border: '1px solid #ddd',
  borderRadius: '3px',
  padding: isFullscreen ? '8px 12px' : '2px 4px',
  fontSize: isFullscreen ? '16px' : '11px',
  fontFamily: 'Source Sans Pro, sans-serif',
  boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
  minWidth: isFullscreen ? '200px' : 'auto',
});

export const tooltipHeaderStyle = (isFullscreen?: boolean) => ({
  color: 'black',
  fontWeight: 500,
  fontFamily: 'Source Sans Pro, sans-serif',
  marginBottom: isFullscreen ? '6px' : '1px',
  fontSize: isFullscreen ? '16px' : 'inherit',
});

export const tooltipRowStyle = (isFullscreen?: boolean) => ({
  color: '#333',
  fontFamily: 'Source Sans Pro, sans-serif',
  display: 'flex',
  justifyContent: 'space-between',
  gap: isFullscreen ? '12px' : '4px',
  lineHeight: isFullscreen ? '1.4' : '1.2',
  fontSize: isFullscreen ? '14px' : 'inherit',
  marginBottom: isFullscreen ? '2px' : '0px',
});

export type ChartMargins = {
  left: number;
  right: number;
  top: number;
  bottom: number;
};

export type AxisPadding = {
  left: number;
  right: number;
  top: number;
  bottom: number;
};

export type ChartDimensions = {
  width: number;
  height: number;
};

export const createChartMargins = (isFullscreen?: boolean): ChartMargins => ({
  left: isFullscreen ? 120 : 60,
  right: isFullscreen ? 60 : 30,
  top: isFullscreen ? 48 : 24,
  bottom: isFullscreen ? 72 : 36,
});

export const createAxisPadding = (isFullscreen?: boolean): AxisPadding => ({
  left: 0,
  right: 0,
  top: -20,
  bottom: isFullscreen ? 6 : 16,
});
