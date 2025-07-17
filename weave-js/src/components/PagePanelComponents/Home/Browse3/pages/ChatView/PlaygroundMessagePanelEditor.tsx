import {MagicButton, MagicTooltip} from '@wandb/weave/common/util/WBMagician2';
import {Button} from '@wandb/weave/components/Button';
import classNames from 'classnames';
import _ from 'lodash';
import React, {useEffect, useMemo, useState} from 'react';
import z from 'zod';

import {StyledTextArea} from '../../StyledTextarea';
import {usePlaygroundContext} from '../PlaygroundPage/PlaygroundContext';
import {DEFAULT_SYSTEM_MESSAGE_CONTENT} from '../PlaygroundPage/usePlaygroundState';
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

const SYSTEM_PROMPT =
  'You are an expert LLM developer & researcher. Your objective is to help the user create a "system prompt" for their own LLM. They are going to provide you with some description or context of what they are interested in build. Assume that may not be perfect. Always produce a useful and clear system prompt that address the user need. NEVER say anything before or after the system prompt. ONLY emit the system prompt.';

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

  const initialContent = useMemo(
    () =>
      _.isString(message.content)
        ? message.content
        : message.content?.join('') ?? '',
    [message.content]
  );

  const [editedContent, setEditedContent] = useState(initialContent);

  useEffect(() => {
    setEditedContent(initialContent);
  }, [initialContent]);

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

  const [isEditable, setIsEditable] = useState(true);

  const handleMagicStream = (content: string, isComplete: boolean) => {
    if (!isComplete) {
      setIsEditable(false);
      setEditedContent(content + '█');
    } else {
      setEditedContent(content);
      setIsEditable(true);
    }
  };

  const contentToRevise =
    editedContent !== DEFAULT_SYSTEM_MESSAGE_CONTENT
      ? editedContent
      : undefined;

  return (
    <div
      className={classNames(
        'w-full pt-[6px]',
        isNested ? 'px-[4px]' : 'px-[16px]'
      )}>
      <StyledTextArea
        value={editedContent}
        onChange={e => setEditedContent(e.target.value)}
        startHeight={320}
        disabled={!isEditable}
      />
      {/* 6px vs. 8px to make up for extra padding from textarea field */}
      <div className="z-100 mt-[6px] flex justify-end gap-[8px]">
        {index === 0 && message.role === 'system' && (
          <>
            <MagicTooltip
              onStream={handleMagicStream}
              systemPrompt={SYSTEM_PROMPT}
              placeholder={'What would you like the model to do?'}
              contentToRevise={contentToRevise}
              responseFormat={z.object({
                systemPrompt: z.string().describe('The system prompt to use'),
              })}>
              <MagicButton size="medium" />
            </MagicTooltip>

            <div className="flex-1"></div>
          </>
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
