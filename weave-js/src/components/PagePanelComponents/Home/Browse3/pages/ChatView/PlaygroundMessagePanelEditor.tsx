import {Button} from '@wandb/weave/components/Button';
import classNames from 'classnames';
import _ from 'lodash';
import React, {useEffect, useMemo, useRef, useState} from 'react';

import {StyledTextArea} from '../../StyledTextarea';
import {usePlaygroundContext} from '../PlaygroundPage/PlaygroundContext';
import {DEFAULT_SYSTEM_MESSAGE_CONTENT} from '../PlaygroundPage/usePlaygroundState';
import {TYPING_CHAR} from '../wfReactInterface/magician';
import {PlaygroundSystemPromptMagicButton} from './PlaygroundSystemPromptMagicButton';
import {Message} from './types';

type PlaygroundMessagePanelEditorProps = {
  editorHeight: number;
  isNested: boolean;
  pendingToolResponseId?: string;
  message: Message;
  index: number;
  choiceIndex?: number;
  setEditorHeight: (height: number | null) => void;
};

export const PlaygroundMessagePanelEditor: React.FC<
  PlaygroundMessagePanelEditorProps
> = ({
  index,
  choiceIndex,
  setEditorHeight,
  editorHeight,
  isNested,
  pendingToolResponseId,
  message,
}) => {
  const {sendMessage, editMessage, editChoice} = usePlaygroundContext();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const initialContent = useMemo(
    () =>
      _.isString(message.content)
        ? message.content
        : message.content?.join('') ?? '',
    [message.content]
  );

  const [editedContent, setEditedContent] = useState(initialContent);
  const [isEditable, setIsEditable] = useState(true);

  useEffect(() => {
    setEditedContent(initialContent);
  }, [initialContent]);

  // Auto-scroll to bottom when content changes during generation
  useEffect(() => {
    if (textareaRef.current && !isEditable) {
      const textarea = textareaRef.current;
      textarea.scrollTop = textarea.scrollHeight;
    }
  }, [editedContent, isEditable]);

  const handleSave = () => {
    if (choiceIndex !== undefined) {
      editChoice?.(choiceIndex, {
        ...message,
        content: editedContent,
      });
    } else {
      editMessage?.(index, {
        ...message,
        content: editedContent,
      });
    }
    setEditorHeight(null);
  };

  const handleCancel = () => {
    setEditedContent(initialContent);
    setEditorHeight(null);
  };

  const handleMagicStream = (
    chunk: string,
    accumulation: string,
    parsedCompletion: any,
    isComplete: boolean
  ) => {
    if (!isComplete) {
      setIsEditable(false);
      setEditedContent(accumulation + TYPING_CHAR);
    } else {
      setEditedContent(accumulation);
      setIsEditable(true);
    }
  };

  const handleMagicCancel = () => {
    // Revert to original content when cancelled
    setEditedContent(initialContent);
    setIsEditable(true);
  };

  const contentToRevise =
    editedContent !== DEFAULT_SYSTEM_MESSAGE_CONTENT
      ? editedContent
      : undefined;

  const showPromptGenerator = index === 0 && message.role === 'system';

  return (
    <div
      className={classNames(
        'w-full pt-[6px]',
        isNested ? 'px-[4px]' : 'px-[16px]'
      )}>
      <StyledTextArea
        ref={textareaRef}
        value={editedContent}
        onChange={e => setEditedContent(e.target.value)}
        startHeight={320}
        disabled={!isEditable}
      />
      {/* 6px vs. 8px to make up for extra padding from textarea field */}
      <div className="z-100 mt-[6px] flex justify-end gap-[8px]">
        {showPromptGenerator && (
          <div className="flex-1">
            <PlaygroundSystemPromptMagicButton
              onStream={handleMagicStream}
              onCancel={handleMagicCancel}
              contentToRevise={contentToRevise}
            />
          </div>
        )}
        <Button variant="ghost" size="medium" onClick={handleCancel}>
          Cancel
        </Button>
        <Button
          variant="primary"
          size="medium"
          onClick={
            pendingToolResponseId
              ? () =>
                  sendMessage?.(
                    'tool',
                    editedContent ?? '',
                    pendingToolResponseId
                  )
              : handleSave
          }>
          Save
        </Button>
      </div>
    </div>
  );
};
