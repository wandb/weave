import {Box, Drawer} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button/Button';
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
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}>
        <Box
          sx={{
            flex: '0 0 auto',
            borderBottom: '1px solid #e0e0e0',
            p: '10px',
            display: 'flex',
            fontWeight: 600,
          }}>
          <Box sx={{flexGrow: 1}}>{title}</Box>
          <Button size="small" variant="ghost" icon="close" onClick={onClose} />
        </Box>

        <Box
          sx={{
            flexGrow: 1,
            overflow: 'auto',
            p: 4,
          }}>
          {children}
        </Box>

        <Box
          sx={{
            display: 'flex',
            flex: '0 0 auto',
            borderTop: '1px solid #e0e0e0',
            p: '10px',
          }}>
          <Button
            onClick={onSave}
            color="primary"
            disabled={saveDisabled}
            className="w-full">
            Create scorer
          </Button>
        </Box>
      </Box>
    </Drawer>
  );
};
