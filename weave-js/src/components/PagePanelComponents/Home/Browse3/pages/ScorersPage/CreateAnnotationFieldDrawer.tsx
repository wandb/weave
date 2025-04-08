import {Box, Typography} from '@mui/material';
import React, {FC, useCallback, useState} from 'react';

import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {ResizableDrawer} from '../common/ResizableDrawer';
import * as AnnotationScorerForm from './AnnotationScorerForm';
import {Button} from '@wandb/weave/components/Button';

// Define typography style with Source Sans Pro font
const typographyStyle = {fontFamily: 'Source Sans Pro'};

interface CreateAnnotationFieldDrawerProps {
  entity: string;
  project: string;
  open: boolean;
  onClose: () => void;
  onSave?: () => void;
}

export const CreateAnnotationFieldDrawer: FC<CreateAnnotationFieldDrawerProps> = ({
  entity,
  project,
  open,
  onClose,
  onSave,
}) => {
  const [formData, setFormData] = useState<any>(null);
  const [isFormValid, setIsFormValid] = useState(false);
  const getClient = useGetTraceServerClientContext();

  const handleFormDataChange = useCallback((isValid: boolean, data: any) => {
    setIsFormValid(isValid);
    setFormData(data);
  }, []);

  const handleSave = useCallback(async () => {
    try {
      await AnnotationScorerForm.onAnnotationScorerSave(
        entity,
        project,
        formData,
        getClient()
      );
      onSave?.();
      onClose();
    } catch (error) {
      console.error('Failed to create annotation field:', error);
    }
  }, [entity, project, formData, getClient, onClose, onSave]);

  return (
    <ResizableDrawer
      open={open}
      onClose={onClose}
      defaultWidth={600}
      headerContent={
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            height: 44,
            minHeight: 44,
            pl: 2,
            pr: 1,
            borderBottom: '1px solid',
            borderColor: 'divider',
          }}>
          <Typography variant="h6" sx={{...typographyStyle, fontWeight: 600}}>
            Create annotation field
          </Typography>
          <Box sx={{display: 'flex', gap: 1}}>
            <Button
              onClick={onClose}
              variant="ghost"
              icon="close"
              tooltip="Close"
            />
          </Box>
        </Box>
      }>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          overflow: 'hidden',
        }}>
        <Box
          sx={{
            p: 2,
            flexGrow: 1,
            overflow: 'auto',
            display: 'flex',
            flexDirection: 'column',
            minHeight: 0,
          }}>
          <AnnotationScorerForm.AnnotationScorerForm
            data={formData}
            onDataChange={handleFormDataChange}
          />
        </Box>
        <Box
          sx={{
            py: 2,
            px: 0,
            borderTop: '1px solid',
            borderColor: 'divider',
            backgroundColor: 'background.paper',
            width: '100%',
            display: 'flex',
            flexShrink: 0,
          }}>
          <Button
            onClick={handleSave}
            variant="primary"
            disabled={!isFormValid}
            tooltip="Create annotation field"
            style={{
              width: '100%',
              margin: '0 16px',
              borderRadius: '4px',
            }}
            twWrapperStyles={{
              width: 'calc(100% - 32px)',
              display: 'block',
            }}>
            Create annotation field
          </Button>
        </Box>
      </Box>
    </ResizableDrawer>
  );
}; 