import {Callout} from '@wandb/weave/components/Callout';
import classNames from 'classnames';
import _ from 'lodash';
import React, {useEffect, useRef, useState} from 'react';

import {usePlaygroundContext} from '../PlaygroundPage/PlaygroundContext';
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
  isChoice?: boolean;
  isNested?: boolean;
  pendingToolResponseId?: string;
};

export const MessagePanel = ({
  index,
  message,
  isStructuredOutput,
  isChoice,
  isNested,
  // The id of the tool call response that is pending
  // If the tool call response is pending, the editor will be shown automatically
  // and on save the tool call response will be updated and sent to the LLM
  pendingToolResponseId,
}: MessagePanelProps) => {
  const [isShowingMore, setIsShowingMore] = useState(false);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const [editorHeight, setEditorHeight] = useState<number | null>(
    pendingToolResponseId ? 100 : null
  );
  const contentRef = useRef<HTMLDivElement>(null);

  const {isPlayground} = usePlaygroundContext();
  useEffect(() => {
    if (contentRef.current) {
      setIsOverflowing(contentRef.current.scrollHeight > 400);
    }
  }, [message.content, contentRef?.current?.scrollHeight]);

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
    <div className={classNames('flex gap-8', {'mt-24': !isTool})}>
      {!isNested && !isSystemPrompt && (
        <div className="w-32 flex-shrink-0">
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
        className={classNames('relative w-full overflow-visible', {
          'rounded-lg': !isNested,
          'border-t border-moon-250': isTool,
          'bg-moon-100': isSystemPrompt || hasToolCalls,
          'bg-cactus-300/[0.24]': isUser,
          'max-w-full': !isUser,
          'max-w-[768px]': isUser,
          'ml-auto': isUser,
          'mr-auto': !isUser,
          'py-8': hasContent,
        })}
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => setIsHovering(false)}>
        <div>
          {isSystemPrompt && (
            <div className="flex justify-between px-16">
              <div className="text-sm text-moon-500">
                {message.role.charAt(0).toUpperCase() + message.role.slice(1)}
              </div>
            </div>
          )}

          {isTool && (
            <div className={classNames('pb-8')}>
              <div className="text-sm font-semibold text-moon-500">
                Response
              </div>
            </div>
          )}

          <div
            ref={contentRef}
            className={classNames('w-full overflow-y-hidden', {
              'max-h-[400px]': !isShowingMore,
              'max-h-full': isShowingMore,
            })}>
            {isPlayground && editorHeight ? (
              <PlaygroundMessagePanelEditor
                message={message}
                index={index}
                isChoice={isChoice ?? false}
                editorHeight={editorHeight}
                isNested={isNested ?? false}
                pendingToolResponseId={pendingToolResponseId}
                setEditorHeight={setEditorHeight}
              />
            ) : (
              <>
                {hasContent && (
                  <div
                    className={classNames(
                      hasToolCalls ? 'pb-8' : '',
                      ' text-sm',
                      {'px-16': isSystemPrompt || isUser}
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
                    className={classNames({
                      'border-t border-moon-250 pt-8': hasContent,
                    })}>
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

          {/* Playground buttons (retry, edit, delete) */}
          {isPlayground && isHovering && !editorHeight && (
            <div
              className={classNames(
                'absolute flex w-full items-center justify-start pt-20',
                isNested ? 'bottom-0' : 'bottom-[-32px]'
              )}>
              <PlaygroundMessagePanelButtons
                index={message.original_index ?? index}
                isChoice={isChoice ?? false}
                isTool={isTool}
                hasContent={hasContent}
                contentRef={contentRef}
                setEditorHeight={setEditorHeight}
                responseIndexes={responseIndexes}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
