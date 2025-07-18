import {Button} from '@wandb/weave/components/Button';
import {MagicButton} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/magician';
import classNames from 'classnames';
import _ from 'lodash';
import React, {useEffect, useMemo, useRef, useState} from 'react';
import z from 'zod';

import {StyledTextArea} from '../../StyledTextarea';
import {usePlaygroundContext} from '../PlaygroundPage/PlaygroundContext';
import {DEFAULT_SYSTEM_MESSAGE_CONTENT} from '../PlaygroundPage/usePlaygroundState';
import {TYPING_CHAR} from '../wfReactInterface/magician';
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

const SYSTEM_PROMPT = `
# Context:
* You are an expert LLM developer & researcher.
* Your objective is to help the user create a "system prompt" for their own LLM. 

# Instructions:
* You will be provided with a description of what the user is interested in building. 
* Assume that the description may not be perfect. 
* Always produce a useful and clear system prompt that addresses the user's need.
* Consider adding structure and organization to the system prompt (personality, instructions, rules, and examples.)
* Output Markdown format (DO NOT EMIT the \`markdown\` code fence markers)

# Rules:
* NEVER ask the user for any information.
* NEVER say anything before or after the system prompt.
* NEVER include any other text or comments. (for example, do not start with "SYSTEM PROMPT:")
* ONLY emit the system prompt.
`;

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

  const handleMagicStream = (content: string, isComplete: boolean) => {
    if (!isComplete) {
      setIsEditable(false);
      setEditedContent(content + TYPING_CHAR);
    } else {
      setEditedContent(content);
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
        {index === 0 && message.role === 'system' && (
          <>
            <MagicButton
              onStream={handleMagicStream}
              onCancel={handleMagicCancel}
              systemPrompt={SYSTEM_PROMPT}
              placeholder={'What are you interested in building?'}
              contentToRevise={contentToRevise}
              _dangerousExtraAttributesToLog={{
                feature: 'playground_prompt',
              }}
              size="medium"
              text="Generate" />

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
