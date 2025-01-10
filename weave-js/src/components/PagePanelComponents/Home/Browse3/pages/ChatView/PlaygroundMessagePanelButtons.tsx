import {toast} from '@wandb/weave/common/components/elements/Toast';
import {Button} from '@wandb/weave/components/Button';
import React from 'react';

import {usePlaygroundContext} from '../PlaygroundPage/PlaygroundContext';

type PlaygroundMessagePanelButtonsProps = {
  index: number;
  choiceIndex?: number;
  isTool: boolean;
  hasContent: boolean;
  contentRef: React.RefObject<HTMLDivElement>;
  setEditorHeight: (height: number | null) => void;
  responseIndexes?: number[];
};

export const PlaygroundMessagePanelButtons: React.FC<
  PlaygroundMessagePanelButtonsProps
> = ({
  index,
  choiceIndex,
  isTool,
  hasContent,
  contentRef,
  setEditorHeight,
  responseIndexes,
}) => {
  const {deleteMessage, deleteChoice, retry} = usePlaygroundContext();

  const handleCopy = async () => {
    if (contentRef.current?.textContent) {
      try {
        await navigator.clipboard.writeText(contentRef.current.textContent);
        toast('Message copied to clipboard');
      } catch (error) {
        toast('Failed to copy message');
      }
    }
  };

  return (
    <div className="ml-auto flex gap-4 rounded-lg pt-[8px]">
      <Button
        variant="ghost"
        size="small"
        startIcon="copy"
        onClick={handleCopy}
        tooltip={!hasContent ? 'No content to copy' : 'Copy message'}
        disabled={!hasContent}>
        Copy
      </Button>
      <Button
        variant="ghost"
        size="small"
        startIcon="randomize-reset-reload"
        onClick={() => retry?.(index, choiceIndex)}
        tooltip={
          !hasContent
            ? 'We currently do not support retrying functions'
            : 'Retry'
        }
        disabled={!hasContent}>
        Retry
      </Button>
      <Button
        variant="ghost"
        size="small"
        startIcon="pencil-edit"
        onClick={() => {
          setEditorHeight(contentRef?.current?.clientHeight ?? null);
        }}
        tooltip={
          !hasContent ? 'We currently do not support editing functions' : 'Edit'
        }
        disabled={!hasContent}>
        Edit
      </Button>
      <Button
        variant="ghost"
        size="small"
        startIcon="delete"
        onClick={() => {
          if (choiceIndex !== undefined) {
            deleteChoice?.(index, choiceIndex);
          } else {
            deleteMessage?.(index, responseIndexes);
          }
        }}
        tooltip={isTool ? 'Tool responses cannot be deleted' : 'Delete message'}
        disabled={isTool}>
        Delete
      </Button>
    </div>
  );
};
