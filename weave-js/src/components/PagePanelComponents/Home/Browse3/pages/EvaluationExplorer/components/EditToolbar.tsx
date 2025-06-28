import React from 'react';
import { GridToolbarContainer } from '@mui/x-data-grid-pro';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import AddIcon from '@mui/icons-material/Add';
import TableRowsIcon from '@mui/icons-material/TableRows';
import ViewColumnIcon from '@mui/icons-material/ViewColumn';
import SettingsIcon from '@mui/icons-material/Settings';

interface EditToolbarProps {
  onAddRow: () => void;
  onAddColumn: () => void;
  onOpenConfig?: () => void;
}

export const EditToolbar: React.FC<EditToolbarProps> = ({ onAddRow, onAddColumn, onOpenConfig }) => {
  return (
    <GridToolbarContainer sx={{ 
      padding: '8px 16px',
      borderBottom: '1px solid #E0E0E0',
      gap: 1,
      display: 'flex',
      justifyContent: 'space-between'
    }}>
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button 
          startIcon={<TableRowsIcon fontSize="small" />} 
          onClick={onAddRow}
          size="small"
          sx={{
            textTransform: 'none',
            fontSize: '0.875rem',
            color: 'text.secondary',
            '&:hover': {
              backgroundColor: 'rgba(0, 0, 0, 0.04)'
            }
          }}
        >
          Add Row
        </Button>
        <Button 
          startIcon={<ViewColumnIcon fontSize="small" />} 
          onClick={onAddColumn}
          size="small"
          sx={{
            textTransform: 'none',
            fontSize: '0.875rem',
            color: 'text.secondary',
            '&:hover': {
              backgroundColor: 'rgba(0, 0, 0, 0.04)'
            }
          }}
        >
          Add Column
        </Button>
      </Box>
      {onOpenConfig && (
        <Button 
          startIcon={<SettingsIcon fontSize="small" />} 
          onClick={onOpenConfig}
          size="small"
          sx={{
            textTransform: 'none',
            fontSize: '0.875rem',
            color: 'text.secondary',
            '&:hover': {
              backgroundColor: 'rgba(0, 0, 0, 0.04)'
            }
          }}
        >
          Config
        </Button>
      )}
    </GridToolbarContainer>
  );
}; 