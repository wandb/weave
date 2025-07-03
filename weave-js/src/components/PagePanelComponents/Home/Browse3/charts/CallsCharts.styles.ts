import {MOON_50} from '@wandb/weave/common/css/color.styles';

export const callsChartsStyles = {
  container: {
    display: 'flex' as const,
    flexDirection: 'column' as const,
    height: '100%',
    width: '100%',
    position: 'relative' as const,
  },

  header: {
    backgroundColor: MOON_50,
    borderBottom: '1px solid rgba(224, 224, 224, 1)',
    padding: '7px 16px 7px 16px',
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

  dropdownContainer: {
    position: 'relative' as const,
  },

  dropdownTrigger: {
    fontSize: '14px',
    fontWeight: 'bold' as const,
    color: '#79808A',
    cursor: 'pointer' as const,
    transition: 'color 0.2s ease',
  },

  dropdownMenu: {
    position: 'absolute' as const,
    top: '100%',
    left: 0,
    zIndex: 1001,
    marginTop: 4,
    minWidth: 80,
    backgroundColor: 'white',
    border: '1px solid #e0e0e0',
    borderRadius: '6px',
    boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
    padding: '4px 0',
  },

  chartsContainer: {
    display: 'flex' as const,
    flexDirection: 'column' as const,
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

export const createDropdownOptionStyle = (
  isSelected: boolean,
  isHovered: boolean
) => ({
  padding: '8px 12px',
  cursor: 'pointer' as const,
  fontSize: '14px',
  backgroundColor: isSelected
    ? '#f0f9ff'
    : isHovered
    ? '#f9fafb'
    : 'transparent',
  color: isSelected ? '#0891b2' : '#374151',
});

export const getDropdownTriggerHoverColor = (isHovered: boolean) =>
  isHovered ? '#038194' : '#79808A';
