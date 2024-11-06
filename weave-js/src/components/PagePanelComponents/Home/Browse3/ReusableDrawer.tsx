import {Box, Button, Drawer, Typography} from '@material-ui/core';
import React, {FC, ReactNode} from 'react';

interface ReusableDrawerProps {
  open: boolean;
  title: string;
  onClose: () => void;
  onSave: () => void;
  saveDisabled?: boolean;
  children: ReactNode;
}

export const ReusableDrawer: FC<ReusableDrawerProps> = ({
  open,
  title,
  onClose,
  onSave,
  saveDisabled,
  children,
}) => {
  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={() => {
        // do nothing
        return;
      }}
      ModalProps={{
        keepMounted: true, // Better open performance on mobile
      }}>
      <Box
        sx={{
          width: '40vw',
          marginTop: '60px',
          height: '100%',
          bgcolor: 'background.paper',
          p: 4,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'auto',
        }}>
        <Typography variant="h6" component="h2">
          {title}
        </Typography>

        <Box sx={{flexGrow: 1, overflow: 'auto', my: 2}}>{children}</Box>

        <Box sx={{display: 'flex', justifyContent: 'flex-end'}}>
          <Button onClick={onClose} style={{marginRight: 8}}>
            Cancel
          </Button>
          <Button
            onClick={onSave}
            variant="contained"
            color="primary"
            disabled={saveDisabled}>
            Save
          </Button>
        </Box>
      </Box>
    </Drawer>
  );
};
