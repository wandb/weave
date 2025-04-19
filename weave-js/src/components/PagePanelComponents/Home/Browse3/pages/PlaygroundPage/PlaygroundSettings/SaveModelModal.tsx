import {Button} from '@wandb/weave/components';
import * as Dialog from '@wandb/weave/components/Dialog';
import {TextField} from '@wandb/weave/components/Form/TextField';
import React, {useEffect, useState} from 'react';

type SaveModelModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSave: (modelName: string) => void;
  initialModelName: string;
};

export const SaveModelModal: React.FC<SaveModelModalProps> = ({
  isOpen,
  onClose,
  onSave,
  initialModelName,
}) => {
  const [modelName, setModelName] = useState(initialModelName);

  // Update local state if the initial name changes (e.g., user switches tabs)
  useEffect(() => {
    if (isOpen) {
      setModelName(initialModelName);
    }
  }, [initialModelName, isOpen]);

  const handleSaveClick = () => {
    if (modelName.trim()) {
      onSave(modelName.trim());
    }
    // Note: onClose will be called by the parent component after successful save
  };

  return (
    <Dialog.Root open={isOpen} onOpenChange={open => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay />
        <Dialog.Content>
          <Dialog.Title>Save Model Configuration</Dialog.Title>
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
              minWidth: '300px',
              marginTop: '16px',
            }}>
            <span style={{fontSize: '14px'}}>Model Name</span>
            <TextField
              autoFocus
              type="text"
              value={modelName}
              onChange={newValue => setModelName(newValue)}
            />
          </div>
          <div
            style={{
              display: 'flex',
              gap: '8px',
              justifyContent: 'flex-end',
              marginTop: '24px',
            }}>
            <Button onClick={onClose} variant="secondary">
              Cancel
            </Button>
            <Button
              onClick={handleSaveClick}
              variant="primary"
              disabled={!modelName.trim()}>
              Save
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};
