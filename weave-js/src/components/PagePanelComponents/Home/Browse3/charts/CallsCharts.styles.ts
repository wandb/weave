import {MOON_50, MOON_100} from '@wandb/weave/common/css/color.styles';

export const callsChartsStyles = {
  container: {
    display: 'flex' as const,
    flexDirection: 'column' as const,
    height: '100%',
    width: '100%',
    position: 'relative' as const,
    backgroundColor: MOON_100,
  },

  header: {
    backgroundColor: MOON_50,
    borderBottom: '1px solid rgba(224, 224, 224, 1)',
    padding: '7px 16px 8px 16px',
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
    flexShrink: 0,
  },

  headerContent: {
    display: 'flex' as const,
    alignItems: 'center' as const,
    justifyContent: 'space-between' as const,
  },

  headerLeft: {
    display: 'flex' as const,
    alignItems: 'center' as const,
    gap: '8px',
  },

  headerText: {
    fontSize: '14px',
    fontWeight: 500,
    color: '#79808A',
  },

  chartsContainer: {
    display: 'grid' as const,
    gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
    gap: 12,
    overflowX: 'hidden' as const,
    overflowY: 'auto' as const,
    padding: '12px',
    flex: 1,
    minHeight: 0,
  },

  emptyState: {
    display: 'flex' as const,
    alignItems: 'center' as const,
    justifyContent: 'center' as const,
    color: '#8F8F8F',
    fontSize: 14,
    width: '100%',
    minHeight: 200,
    textAlign: 'center' as const,
    padding: '40px 20px',
  },
};
