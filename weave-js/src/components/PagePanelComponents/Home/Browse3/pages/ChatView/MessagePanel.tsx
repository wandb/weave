import {Button} from '@wandb/weave/components/Button';
import {Callout} from '@wandb/weave/components/Callout';
import classNames from 'classnames';
import _ from 'lodash';
import React, {useEffect, useRef, useState} from 'react';

import {usePlaygroundContext} from '../PlaygroundPage/PlaygroundChat/PlaygroundContext';
import {TextArea} from '../PlaygroundPage/Textarea';
import {MessagePanelPart} from './MessagePanelPart';
import {ShowMoreButton} from './ShowMoreButton';
import {ToolCalls} from './ToolCalls';
import {Message} from './types';

type MessagePanelProps = {
  index: number;
  message: Message;
  isStructuredOutput?: boolean;
  isChoice?: boolean;
  isNested?: boolean;
  toolResponseId?: string;
};

export const MessagePanel = ({
  index,
  message,
  isStructuredOutput,
  isChoice,
  isNested,
  toolResponseId,
}: MessagePanelProps) => {
  const [isShowingMore, setIsShowingMore] = useState(false);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const [editorHeight, setEditorHeight] = useState<number | null>(
    toolResponseId ? 100 : null
  );
  const contentRef = useRef<HTMLDivElement>(null);

  const {
    isPlayground,
    deleteMessage,
    editMessage,
    deleteChoice,
    editChoice,
    retry,
    sendMessage,
  } = usePlaygroundContext();
  useEffect(() => {
    if (contentRef.current) {
      setIsOverflowing(contentRef.current.scrollHeight > 400);
    }
  }, [message.content]);

  const isUser = message.role === 'user';
  const isSystemPrompt = message.role === 'system';
  const isTool = message.role === 'tool';
  const hasToolCalls = message.tool_calls && message.tool_calls.length > 0;
  const hasContent = message.content && message.content.length > 0;

  const bg = isUser ? 'bg-cactus-300/[0.24]' : '';
  const border = isSystemPrompt ? 'border border-moon-250 rounded-lg' : '';
  const justification = isUser ? 'ml-auto' : 'mr-auto';
  const maxHeight = isShowingMore ? 'max-h-full' : 'max-h-[400px]';
  const maxWidth = isSystemPrompt || isNested ? 'w-full' : 'max-w-3xl';
  const toolWidth =
    isTool || hasToolCalls || isStructuredOutput || editorHeight ? 'w-3/4' : '';

  const capitalizedRole =
    message.role.charAt(0).toUpperCase() + message.role.slice(1);

  const [editedContent, setEditedContent] = useState(
    _.isString(message.content) ? message.content : message.content?.join('')
  );

  // Add this useEffect hook
  useEffect(() => {
    setEditedContent(
      _.isString(message.content) ? message.content : message.content?.join('')
    );
  }, [message.content]);

  const handleSave = () => {
    if (isChoice) {
      editChoice?.(index, {
        message: {content: editedContent},
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
    setEditedContent(
      _.isString(message.content) ? message.content : message.content?.join('')
    );
    setEditorHeight(null);
  };

  return (
    <div className={classNames('flex gap-8', isTool ? '' : 'mt-32')}>
      {!isNested && (
        <div className="w-40">
          {!isUser && !isTool && (
            <Callout
              size="small"
              icon="robot-service-member"
              color="moon"
              className="h-32 w-32"
            />
          )}
        </div>
      )}

      <div
        className={classNames(
          'relative overflow-visible py-8',
          bg,
          maxWidth,
          justification,
          isOverflowing && isShowingMore ? 'pb-40' : '',
          toolWidth,
          isTool ? 'border-t border-moon-250' : '',
          border
        )}
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => setIsHovering(false)}>
        <div>
          {isSystemPrompt && (
            <div className="flex justify-between px-16">
              <div className="text-base font-semibold">{capitalizedRole}</div>
            </div>
          )}

          {isTool && (
            <div className={classNames(isNested ? '' : 'px-16', 'pb-8')}>
              <div className="text-sm font-semibold text-moon-500">
                Response
              </div>
            </div>
          )}

          <div
            ref={contentRef}
            className={classNames('w-full overflow-y-hidden', maxHeight)}>
            {editorHeight ? (
              <div
                className={classNames(
                  'w-full pt-16 text-sm',
                  isNested ? 'px-2' : 'px-16'
                )}>
                <TextArea
                  value={editedContent}
                  onChange={e => setEditedContent(e.target.value)}
                  style={{
                    minHeight: `${editorHeight}px`,
                  }}
                />
                <div className="z-100 mt-8 flex justify-end gap-8">
                  <Button variant="quiet" size="small" onClick={handleCancel}>
                    Cancel
                  </Button>
                  <Button
                    variant="primary"
                    size="small"
                    onClick={
                      toolResponseId
                        ? () =>
                            sendMessage?.(
                              'tool',
                              editedContent ?? '',
                              toolResponseId
                            )
                        : handleSave
                    }>
                    Save
                  </Button>
                </div>
              </div>
            ) : (
              <>
                {hasContent && (
                  <div
                    className={classNames(
                      hasToolCalls ? 'pb-8' : '',
                      ' text-sm',
                      isNested ? '' : 'px-16'
                    )}>
                    {_.isString(message.content) ? (
                      <MessagePanelPart
                        value={message.content}
                        isStructuredOutput={isStructuredOutput}
                      />
                    ) : (
                      message.content!.map((p, i) => (
                        <MessagePanelPart key={i} value={p} />
                      ))
                    )}
                  </div>
                )}
                {hasToolCalls && (
                  <div
                    className={classNames(
                      hasContent ? 'border-t border-moon-250 pt-8' : ''
                    )}>
                    <ToolCalls toolCalls={message.tool_calls!} />
                  </div>
                )}
              </>
            )}
          </div>

          {isOverflowing && !editorHeight && (
            <ShowMoreButton
              isUser={isUser}
              isShowingMore={isShowingMore}
              setIsShowingMore={setIsShowingMore}
            />
          )}

          {isPlayground && isHovering && !editorHeight && (
            <div
              className={classNames(
                'absolute right-0 flex w-full items-center justify-end pt-20',
                isNested ? 'bottom-0' : 'bottom-[-32px]'
              )}>
              <div className="z-10 flex gap-4 rounded-lg border border-moon-250 bg-white p-4">
                <Button
                  variant="quiet"
                  size="small"
                  startIcon="randomize-reset-reload"
                  onClick={() => retry?.(index, isChoice)}>
                  Retry
                </Button>
                <Button
                  variant="quiet"
                  size="small"
                  startIcon="pencil-edit"
                  onClick={() => {
                    setEditorHeight(
                      contentRef?.current?.clientHeight
                        ? // Accounts for padding and save buttons
                          contentRef.current.clientHeight - 56
                        : null
                    );
                  }}
                  tooltip={
                    !hasContent
                      ? 'We currently do not support editing functions'
                      : 'Edit'
                  }
                  disabled={!hasContent}>
                  Edit
                </Button>
                <Button
                  variant="quiet"
                  size="small"
                  startIcon="delete"
                  onClick={() => {
                    if (isChoice) {
                      deleteChoice?.(index);
                    } else {
                      deleteMessage?.(index);
                    }
                  }}
                  tooltip={
                    isTool
                      ? 'Tool responses cannot be deleted'
                      : 'Delete message'
                  }
                  disabled={isTool}>
                  Delete
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
