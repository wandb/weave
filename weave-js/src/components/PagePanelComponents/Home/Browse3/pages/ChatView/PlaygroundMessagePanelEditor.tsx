import {Button} from '@wandb/weave/components/Button';
import {MagicButton, MagicTooltip} from '@wandb/weave/WBMagician2';
import classNames from 'classnames';
import _ from 'lodash';
import React, {useEffect, useMemo, useState} from 'react';

import {StyledTextArea} from '../../StyledTextarea';
import {usePlaygroundContext} from '../PlaygroundPage/PlaygroundContext';
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

  const [magicAnchorEl, setMagicAnchorEl] = useState<HTMLElement | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

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

  const handleMagicStream = (content: string, isComplete: boolean) => {
    setEditedContent(content);
    if (isComplete) {
      setIsGenerating(false);
    } else {
      setIsGenerating(true);
    }
  };

  const handleMagicError = (error: Error) => {
    console.error('Magic generation error:', error);
    setIsGenerating(false);
  };

  // Determine magic button state
  const getMagicButtonState = () => {
    if (isGenerating) return 'generating';
    if (magicAnchorEl) return 'tooltipOpen';
    return 'default';
  };

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
      />
      {/* 6px vs. 8px to make up for extra padding from textarea field */}
      <div className="z-100 mt-[6px] flex justify-end gap-[8px]">
        {index === 0 && message.role === 'system' && (
          <>
            <MagicButton
              size="medium"
              onClick={e => setMagicAnchorEl(e.currentTarget)}
              state={getMagicButtonState()}
              onCancel={() => setMagicAnchorEl(null)}
              iconOnly
            />

            <MagicTooltip
              anchorEl={magicAnchorEl}
              open={Boolean(magicAnchorEl)}
              onClose={() => setMagicAnchorEl(null)}
              onStream={handleMagicStream}
              onError={handleMagicError}
              systemPrompt={
                'You are an expert LLM developer & researcher. Your objective is to help the user create a "system prompt" for their own LLM. They are going to provide you with some description or context of what they are interested in build. Assume that may not be perfect. Always produce a useful and clear system prompt that address the user need. NEVER say anything before or after the system prompt. ONLY emit the system prompt.'
              }
              placeholder={
                'Describe the system prompt you want to create - for example: "A system prompt for a LLM that can help me build a new website."'
              }
            />

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
