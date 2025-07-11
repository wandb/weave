import {Callout} from '@wandb/weave/components/Callout';
import classNames from 'classnames';
import _ from 'lodash';
import React, {useEffect, useRef, useState} from 'react';

import {usePlaygroundContext} from '../PlaygroundPage/PlaygroundContext';
import {useAnimatedText} from './hooks';
import {MessagePanelPart} from './MessagePanelPart';
import {PlaygroundMessagePanelButtons} from './PlaygroundMessagePanelButtons';
import {PlaygroundMessagePanelEditor} from './PlaygroundMessagePanelEditor';
import {ShowMoreButton} from './ShowMoreButton';
import {ToolCalls} from './ToolCalls';
import {Message, ToolCall} from './types';

type MessagePanelProps = {
  index: number;
  message: Message;
  isStructuredOutput?: boolean;
  choiceIndex?: number;
  isNested?: boolean;
  pendingToolResponseId?: string;
  messageHeader?: React.ReactNode;
  isLast?: boolean;
};

export const MessagePanel = ({
  index,
  message,
  isStructuredOutput,
  choiceIndex,
  isNested,
  // The id of the tool call response that is pending
  // If the tool call response is pending, the editor will be shown automatically
  // and on save the tool call response will be updated and sent to the LLM
  pendingToolResponseId,
  messageHeader,
  isLast = false,
}: MessagePanelProps) => {
  // If the message is the last message, we show the whole message by default
  const [isShowingMore, setIsShowingMore] = useState(false);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const [editorHeight, setEditorHeight] = useState<number | null>(
    pendingToolResponseId ? 100 : null
  );
  const contentRef = useRef<HTMLDivElement>(null);

  const {isPlayground, isStreaming} = usePlaygroundContext();

  // Determine if we should animate text
  const shouldAnimateText = Boolean(
    isPlayground &&
      isStreaming &&
      isLast &&
      contentRef?.current &&
      (message.content || (message.tool_calls && message.tool_calls.length > 0))
  );

  // Use animated text for the message content
  const messageText = _.isString(message.content) ? message.content : '';
  const {displayedText, isAnimating} = useAnimatedText(
    messageText,
    shouldAnimateText,
    50
  );

  useEffect(() => {
    if (contentRef.current) {
      setIsOverflowing(contentRef.current.scrollHeight > 400);
    }
  }, [message.content, contentRef?.current?.scrollHeight]);

  // Set isShowingMore to true when editor is opened
  useEffect(() => {
    if (editorHeight !== null && !isShowingMore) {
      setIsShowingMore(true);
    }
  }, [editorHeight, isShowingMore]);

  useEffect(() => {
    if (isLast && !isShowingMore && isOverflowing && isPlayground) {
      setIsShowingMore(true);
    }
  }, [isLast, isShowingMore, isOverflowing, isPlayground]);

  const isUser = message.role === 'user';
  const isSystemPrompt = message.role === 'system';
  const isTool = message.role === 'tool';
  const hasToolCalls =
    message.tool_calls != null && message.tool_calls.length > 0;
  const hasContent = message.content != null && message.content.length > 0;

  const responseIndexes: number[] | undefined = hasToolCalls
    ? message
        .tool_calls!.map(
          (toolCall: ToolCall) => toolCall.response?.original_index
        )
        .filter((idx): idx is number => idx !== undefined)
    : undefined;

  return (
    <div
      className={classNames('group', {
        'mb-[16px]': !isNested,
        'mb-[0]': isNested,
      })}>
      <div className="flex gap-[16px]">
        {!isNested && !isSystemPrompt && (
          <div className="w-32 flex-shrink-0">
            {!isUser && !isTool && (
              <Callout
                size="x-small"
                icon="robot-service-member"
                color="moon"
                className="mt-[4px] h-32 w-32 bg-moon-100"
              />
            )}
          </div>
        )}

        <div
          className={classNames('relative w-full overflow-visible', {
            'rounded-lg': !isNested,
            'border-t border-moon-250': isTool,
            'bg-moon-100': isSystemPrompt || isTool,
            'bg-cactus-300/[0.24]': isUser,
            'max-w-full': !isUser,
            'max-w-[768px]': isUser,
            'ml-auto': isUser,
            'mr-auto': !isUser,
            'py-[16px]': hasContent,
            'pb-[4px] pt-[8px]': !isUser && !isTool && !isSystemPrompt,
          })}>
          <div
            className={classNames({
              'pb-[16px]': hasToolCalls && hasContent,
            })}>
            {isSystemPrompt && (
              <div className="flex justify-between px-[16px]">
                <div className="text-sm text-moon-500">
                  {message.role.charAt(0).toUpperCase() + message.role.slice(1)}
                </div>
              </div>
            )}

            {isTool && (
              <div className={classNames('pb-8')}>
                <div className="text-[14px] font-semibold text-moon-500">
                  Response
                </div>
              </div>
            )}

            <div
              ref={contentRef}
              className={classNames('w-full overflow-y-hidden', {
                'max-h-[400px]': !isShowingMore && !editorHeight,
                'max-h-full': isShowingMore || editorHeight,
              })}>
              {messageHeader}
              {isPlayground && editorHeight ? (
                <PlaygroundMessagePanelEditor
                  message={message}
                  index={index}
                  choiceIndex={choiceIndex}
                  editorHeight={editorHeight}
                  isNested={isNested ?? false}
                  pendingToolResponseId={pendingToolResponseId}
                  setEditorHeight={setEditorHeight}
                />
              ) : (
                <>
                  {hasContent && (
                    <div
                      className={classNames(hasToolCalls ? 'pb-8' : '', {
                        'px-16': isSystemPrompt || isUser,
                      })}>
                      {_.isString(message.content) ? (
                        <MessagePanelPart
                          value={
                            shouldAnimateText ? displayedText : message.content
                          }
                          isStructuredOutput={isStructuredOutput}
                          showCursor={shouldAnimateText && isAnimating}
                          role={message.role}
                        />
                      ) : (
                        message.content!.map((p, i) => (
                          <MessagePanelPart
                            key={i}
                            value={p}
                            role={message.role}
                          />
                        ))
                      )}
                    </div>
                  )}
                </>
              )}
            </div>

            {isOverflowing && !editorHeight && (
              <ShowMoreButton
                isUser={isUser}
                isSystemPrompt={isSystemPrompt}
                isNested={isNested}
                isShowingMore={isShowingMore}
                setIsShowingMore={setIsShowingMore}
              />
            )}
          </div>
          {hasToolCalls && (
            <div
              className={classNames({
                'border-t border-moon-250 pt-8': hasContent,
              })}>
              <ToolCalls toolCalls={message.tool_calls!} />
            </div>
          )}
        </div>
      </div>

      {/* Playground buttons (retry, edit, delete) - using group and group-hover to control opacity. */}
      {isPlayground && !editorHeight ? (
        <div className="flex w-full items-center justify-start opacity-0 group-hover:opacity-100">
          <PlaygroundMessagePanelButtons
            index={message.original_index ?? index}
            choiceIndex={choiceIndex}
            isTool={isTool}
            hasContent={hasContent}
            contentRef={contentRef}
            setEditorHeight={setEditorHeight}
            responseIndexes={responseIndexes}
          />
        </div>
      ) : null}
    </div>
  );
};
