import {Callout} from '@wandb/weave/components/Callout';
import classNames from 'classnames';
import _ from 'lodash';
import React, {useEffect, useRef, useState} from 'react';

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
  pendingToolResponseId?: string;
};

export const MessagePanel = ({
  message,
  isStructuredOutput,
  isNested,
}: MessagePanelProps) => {
  const [isShowingMore, setIsShowingMore] = useState(false);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (contentRef.current) {
      setIsOverflowing(contentRef.current.scrollHeight > 400);
    }
  }, [message.content]);

  const isUser = message.role === 'user';
  const isSystemPrompt = message.role === 'system';
  const isTool = message.role === 'tool';
  const hasToolCalls =
    message.tool_calls != null && message.tool_calls.length > 0;
  const hasContent = message.content != null && message.content.length > 0;

  return (
    <div className={classNames('flex gap-8', {'mt-24': !isTool})}>
      {!isNested && (
        <div className="w-32">
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
        className={classNames('relative overflow-visible', {
          'pb-40': isOverflowing && isShowingMore,
          'border-t border-moon-250': isTool,
          'rounded-lg border border-moon-250': isSystemPrompt,
          'bg-cactus-300/[0.24]': isUser,
          'w-full': !isUser,
          'max-w-3xl': isUser,
          'ml-auto': isUser,
          'mr-auto': !isUser,
          'py-8': hasContent,
        })}>
        <div>
          {isSystemPrompt && (
            <div className="flex justify-between px-16">
              <div className="text-base font-semibold">
                {message.role.charAt(0).toUpperCase() + message.role.slice(1)}
              </div>
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
            className={classNames('w-full overflow-y-hidden', {
              'max-h-[400px]': !isShowingMore,
              'max-h-full': isShowingMore,
            })}>
            {hasContent && (
              <div
                className={classNames(hasToolCalls ? 'pb-8' : '', ' text-sm', {
                  'px-16': isSystemPrompt || isUser,
                })}>
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
          </div>

          {isOverflowing && (
            <ShowMoreButton
              isUser={isUser}
              isShowingMore={isShowingMore}
              setIsShowingMore={setIsShowingMore}
            />
          )}
        </div>
      </div>
    </div>
  );
};
