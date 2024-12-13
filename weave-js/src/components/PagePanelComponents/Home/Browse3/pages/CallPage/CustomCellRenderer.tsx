import {Box} from '@mui/material';
import {GridRenderCellParams} from '@mui/x-data-grid-pro';
import {Icon} from '@wandb/weave/components/Icon';
import React, {useState} from 'react';

interface CustomCellProps extends GridRenderCellParams {
  isEdited?: boolean;
  isDeleted?: boolean;
  isNew?: boolean;
}

const CustomCellRenderer: React.FC<CustomCellProps> = ({
  value,
  isEdited = false,
  isDeleted = false,
  isNew = false,
  api,
  id,
  field,
  ...other
}) => {
  const handleEditClick = (event: React.MouseEvent) => {
    event.stopPropagation();
    api.startCellEditMode({id, field});
  };

  const [isHovered, setIsHovered] = useState(false);

  return (
    <Box
      onClick={handleEditClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      sx={{
        position: 'relative',
        height: '100%',
        width: '100%',
        fontFamily: '"Source Sans Pro", sans-serif',
        fontSize: '14px',
        lineHeight: '1.5',
        cursor: 'pointer',
        backgroundColor: isDeleted
          ? 'rgba(255, 0, 0, 0.1)'
          : isEdited
          ? 'rgba(0, 128, 128, 0.2)' // teal/300 20% for light mode
          : isNew
          ? 'rgba(0, 255, 0, 0.1)'
          : 'transparent',
        opacity: isDeleted ? 0.5 : 1,
        textDecoration: isDeleted ? 'line-through' : 'none',
        borderRadius: '2px',
        transition: 'background-color 0.5s ease',
        padding: '12px',
        '&:hover': {
          backgroundColor: 'rgba(0, 0, 0, 0.1)',
        },
      }}>
      {isHovered && (
        <Box
          sx={{
            position: 'absolute',
            top: 12,
            right: 12,
            opacity: 0,
            transition: 'opacity 0.2s ease',
            cursor: 'pointer',
            animation: isHovered ? 'fadeIn 0.2s ease forwards' : 'none',
            '@keyframes fadeIn': {
              '0%': {
                opacity: 0,
              },
              '100%': {
                opacity: 0.5,
              },
            },
            '&:hover': {
              opacity: 0.8,
            },
          }}>
          <Icon name="pencil-edit" size="medium" />
        </Box>
      )}
      {value}
    </Box>
  );
};

export default CustomCellRenderer;
