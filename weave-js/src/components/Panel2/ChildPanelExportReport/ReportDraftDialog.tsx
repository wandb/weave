import * as Dialog from '@wandb/weave/components/Dialog';
import React from 'react';
import Timeago from 'react-timeago';

import {Button} from '../../Button';

type ReportDraftDialogProps = {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  draftCreatedAt: string;
  onCancel: () => void;
  onContinue: () => void;
  onDiscard: () => void;
};

export const ReportDraftDialog = ({
  isOpen,
  setIsOpen,
  draftCreatedAt,
  onCancel,
  onContinue,
  onDiscard,
}: ReportDraftDialogProps) => {
  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="z-[999]" />
        <Dialog.Content
          className="z-[999] w-[540px]"
          onEscapeKeyDown={onCancel}
          onInteractOutside={onCancel}>
          <Dialog.Title>Add to active draft?</Dialog.Title>
          <Dialog.Description className="mb-24 mt-8">
            You started a draft for this report{' '}
            <Timeago date={draftCreatedAt + 'Z'} />. Would you like to continue
            editing this draft or discard it and start a new one?
          </Dialog.Description>
          <Button className="mr-8" onClick={onContinue}>
            Add to active draft
          </Button>
          <Button variant="destructive" onClick={onDiscard}>
            Discard and start new draft
          </Button>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};
