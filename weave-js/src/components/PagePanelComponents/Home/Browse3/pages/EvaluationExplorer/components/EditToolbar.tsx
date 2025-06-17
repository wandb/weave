import React from 'react';
import { GridToolbarContainer } from '@mui/x-data-grid-pro';
import Button from '@mui/material/Button';
import AddIcon from '@mui/icons-material/Add';

interface EditToolbarProps {
  onAddRow: () => void;
  onAddColumn: () => void;
}

export const EditToolbar: React.FC<EditToolbarProps> = ({ onAddRow, onAddColumn }) => {
  return (
    <GridToolbarContainer>
      <Button color="primary" startIcon={<AddIcon />} onClick={onAddRow}>
        Add Row
      </Button>
      <Button color="primary" startIcon={<AddIcon />} onClick={onAddColumn}>
        Add Column
      </Button>
    </GridToolbarContainer>
  );
}; 