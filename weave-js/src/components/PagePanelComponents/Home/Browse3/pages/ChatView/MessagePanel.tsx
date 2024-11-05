import {Callout} from '@wandb/weave/components/Callout';
import classNames from 'classnames';
import _ from 'lodash';
import React, {useEffect, useRef, useState} from 'react';

import {MessagePanelPart} from './MessagePanelPart';
import {ShowMoreButton} from './ShowMoreButton';
import {ToolCalls} from './ToolCalls';
import {Message} from './types';

type MessagePanelProps = {
  message: Message;
  isStructuredOutput?: boolean;
};

export const MessagePanel = ({
  message,
  isStructuredOutput,
}: MessagePanelProps) => {
  const isUser = message.role === 'user';
  const isTool = message.role === 'tool';
  const isSystemPrompt = message.role === 'system';
  const hasToolCalls = !!message.tool_calls && message.tool_calls.length > 0;
  const hasContent = !!message.content && message.content.length > 0;

  const [isShowingMore, setIsShowingMore] = useState(false);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (contentRef.current) {
      setIsOverflowing(contentRef.current.scrollHeight > 400);
    }
  }, [message.content]);

  return (
    <div className={classNames('flex gap-8', {'mt-32': !isTool})}>
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
      <div
        className={classNames('relative overflow-visible py-8', {
          'border-t border-moon-250': isTool,
          // System prompt styles, full width with border
          'w-full rounded-lg border border-moon-250': isSystemPrompt,
          // Max width for non-system prompts
          'max-w-3xl': !isSystemPrompt,
          'w-3/4': isTool || isStructuredOutput || hasToolCalls,
          // Justify the message to the right if it's a user message, add cactus background
          'ml-auto bg-cactus-300/[0.24]': isUser,
          // Justify the message to the left if it's not a user message
          'mr-auto': !isUser,
          'pb-40': isOverflowing && isShowingMore,
        })}>
        {isSystemPrompt && (
          // We only show the role for system prompts
          <div className="flex justify-between px-16">
            <div className="text-base font-semibold">
              {message.role.charAt(0).toUpperCase() + message.role.slice(1)}
            </div>
          </div>
        )}
        <div
          ref={contentRef}
          className={classNames('w-full overflow-y-hidden px-16', {
            'max-h-[400px]': !isShowingMore,
            'max-h-full': isShowingMore,
          })}>
          {hasContent && (
            <div>
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
          {hasToolCalls && <ToolCalls toolCalls={message.tool_calls!} />}
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
  );
};
