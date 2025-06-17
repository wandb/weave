import React from 'react';
import { 
  Box, 
  Typography, 
  IconButton, 
  Divider,
  Paper
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { Close, ChevronLeft, ChevronRight } from '@mui/icons-material';
import TextField from '@mui/material/TextField';

interface DetailPanel {
  id: string;
  title: string;
  content: React.ReactNode;
  width?: number | string;
  onClose?: () => void;
}

interface DetailDrawerProps {
  open: boolean;
  onClose?: () => void;
  title: string;
  width?: number | string;
  children: React.ReactNode;
  side?: 'left' | 'right';
  showCloseButton?: boolean;
  headerExtra?: React.ReactNode;
  panels?: DetailPanel[];
}

export const DetailDrawer: React.FC<DetailDrawerProps> = ({ 
  open, 
  onClose, 
  title,
  width = 400,
  children,
  side = 'right',
  showCloseButton = true,
  headerExtra,
  panels = []
}) => {
  if (!open) return null;

  // Calculate total width including all panels
  const baseWidth = typeof width === 'number' ? width : 400;
  const totalWidth = panels.reduce((acc, panel) => {
    const panelWidth = typeof panel.width === 'number' ? panel.width : 400;
    return acc + panelWidth;
  }, baseWidth);

  // Calculate the offset for panels opening to the left
  const panelsWidth = panels.reduce((acc, panel) => {
    const panelWidth = typeof panel.width === 'number' ? panel.width : 400;
    return acc + panelWidth;
  }, 0);

  return (
    <Box
      sx={{
        position: 'absolute',
        top: 0,
        right: side === 'right' ? 0 : undefined,
        left: side === 'left' ? 0 : undefined,
        width: totalWidth,
        height: '100%',
        display: 'flex',
        flexDirection: 'row',
        backgroundColor: 'white',
        boxShadow: '-4px 0 16px rgba(0, 0, 0, 0.08)',
        borderLeft: '1px solid #E0E0E0',
        zIndex: 10,
        transform: open ? 'translateX(0)' : (side === 'right' ? 'translateX(100%)' : 'translateX(-100%)'),
        transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
      }}
    >
      {/* Additional panels (rendered first, on the left) */}
      {panels.map((panel, index) => (
        <Box
          key={panel.id}
          sx={{
            width: panel.width || 400,
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: 'white',
            borderLeft: index > 0 ? '1px solid #E0E0E0' : undefined,
            borderRight: '1px solid #E0E0E0'
          }}
        >
          {/* Panel Header */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: 2,
              borderBottom: '1px solid #E0E0E0',
              backgroundColor: 'white'
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {panel.onClose && (
                <IconButton
                  size="small"
                  onClick={panel.onClose}
                  sx={{ 
                    '&:hover': { 
                      backgroundColor: 'rgba(0, 0, 0, 0.04)' 
                    } 
                  }}
                >
                  <ChevronRight />
                </IconButton>
              )}
              <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1.125rem' }}>
                {panel.title}
              </Typography>
            </Box>
            <Box sx={{ width: 40 }} />
          </Box>

          {/* Panel Content */}
          <Box sx={{ flex: 1, overflowY: 'auto' }}>
            {panel.content}
          </Box>
        </Box>
      ))}

      {/* Main panel (rendered last, on the right) */}
      <Box
        sx={{
          width: baseWidth,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: '#FAFAFA'
        }}
      >
        {/* Header */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: 2,
            borderBottom: '1px solid #E0E0E0',
            backgroundColor: '#FFFFFF'
          }}
        >
          <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1.125rem' }}>
            {title}
          </Typography>
          {headerExtra}
          {showCloseButton && onClose && (
            <IconButton
              size="small"
              onClick={onClose}
              sx={{ 
                '&:hover': { 
                  backgroundColor: 'rgba(0, 0, 0, 0.04)' 
                } 
              }}
            >
              <Close />
            </IconButton>
          )}
        </Box>

        {/* Content */}
        <Box sx={{ flex: 1, overflowY: 'auto' }}>
          {children}
        </Box>
      </Box>
    </Box>
  );
};

interface DrawerSectionProps {
  title?: string;
  children: React.ReactNode;
  noPadding?: boolean;
}

// Helper components for consistent drawer sections
export const DrawerSection: React.FC<DrawerSectionProps> = ({ 
  children,
  noPadding = false
}) => (
  <Box sx={{ 
    padding: noPadding ? 0 : 3,
    '&:not(:last-child)': {
      borderBottom: '1px solid #E0E0E0'
    }
  }}>
    {children}
  </Box>
);

export const DrawerFormField: React.FC<{
  label: string;
  description?: string;
  required?: boolean;
  children: React.ReactNode;
}> = ({ label, description, required, children }) => (
  <Box sx={{ marginBottom: 3 }}>
    <Typography 
      variant="subtitle2" 
      sx={{ 
        fontSize: '0.875rem', 
        fontWeight: 600, 
        marginBottom: 1,
        color: 'text.primary'
      }}
    >
      {label}
      {required && <span style={{ color: '#D32F2F', marginLeft: 4 }}>*</span>}
    </Typography>
    {children}
    {description && (
      <Typography 
        variant="caption" 
        sx={{ 
          display: 'block',
          marginTop: 0.5,
          color: 'text.secondary',
          fontSize: '0.75rem'
        }}
      >
        {description}
      </Typography>
    )}
  </Box>
); 