import React from 'react';
import { 
  Box, 
  Typography, 
  IconButton, 
  Divider,
  Paper
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';

interface DetailDrawerProps {
  open: boolean;
  onClose?: () => void;
  title: string;
  width?: number | string;
  children: React.ReactNode;
  side?: 'left' | 'right';
  showCloseButton?: boolean;
  headerExtra?: React.ReactNode;
}

export const DetailDrawer: React.FC<DetailDrawerProps> = ({ 
  open,
  onClose,
  title,
  width = 400,
  children,
  side = 'right',
  showCloseButton = true,
  headerExtra
}) => {
  if (!open) return null;

  return (
    <Paper
      elevation={3}
      sx={{
        position: 'absolute',
        top: 0,
        right: side === 'right' ? 0 : undefined,
        left: side === 'left' ? 0 : undefined,
        width,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: side === 'left' ? '#FAFAFA' : 'white',
        borderLeft: side === 'right' ? '1px solid #E0E0E0' : undefined,
        borderRight: side === 'left' ? '1px solid #E0E0E0' : undefined,
        zIndex: 10,
        transform: open ? 'translateX(0)' : (side === 'right' ? 'translateX(100%)' : 'translateX(-100%)'),
        transition: 'transform 0.3s ease-in-out'
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
          backgroundColor: '#FAFAFA'
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
            <CloseIcon />
          </IconButton>
        )}
      </Box>

      {/* Content */}
      <Box sx={{ 
        flex: 1, 
        overflowY: 'auto', 
        overflowX: 'hidden'
      }}>
        {children}
      </Box>
    </Paper>
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