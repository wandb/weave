import {Button} from '@wandb/weave/components/Button';
import {Callout} from '@wandb/weave/components/Callout';
import classNames from 'classnames';
import _ from 'lodash';
import React, {useEffect, useRef, useState} from 'react';

import {MessagePanelPart} from './MessagePanelPart';
import {ShowMoreButton} from './ShowMoreButton';
import {ToolCalls} from './ToolCalls';
import {Message} from './types';

type ToolCallProps = {
  message: Message;
  isStructuredOutput?: boolean;
};

export const ToolCallPanel = ({message, isStructuredOutput}: ToolCallProps) => {
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
  const hasToolCalls = message.tool_calls;

  const bg = isUser ? 'bg-cactus-300/[0.24]' : 'bg-moon-50';
  const justification = isUser ? 'ml-auto' : 'mr-auto';
  const maxHeight = isShowingMore ? 'max-h-full' : 'max-h-[400px]';
  const maxWidth = isSystemPrompt ? 'w-full' : 'max-w-3xl';
  const toolWidth = isTool || hasToolCalls ? 'w-3/4' : '';

  const capitalizedRole =
    message.role.charAt(0).toUpperCase() + message.role.slice(1);

  return (
    <div className={classNames('flex gap-8', isTool ? '' : 'mt-32')}>
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
        className={classNames(
          'relative py-8',
          bg,
          maxWidth,
          justification,
          isOverflowing && isShowingMore ? 'pb-40' : '',
          toolWidth,
          hasToolCalls ? 'border-b border-moon-250' : ''
        )}>
        {hasToolCalls && (
          <div className="px-16 pb-8">
            <div className="flex justify-between">
              <div className="font-base text-base text-moon-500">Function</div>
              <Button icon="copy" variant="quiet" size="small" tooltip="Copy" />
            </div>
          </div>
        )}
        <div
          className={classNames(
            'px-16',
            hasToolCalls ? 'border-t border-moon-250 pt-8' : ''
          )}>
          {isSystemPrompt && (
            <div className="flex justify-between">
              <div className="text-base font-semibold">{capitalizedRole}</div>
            </div>
          )}

          <div
            ref={contentRef}
            className={classNames('overflow-y-hidden', maxHeight)}>
            {message.content && (
              <div className="text-sm">
                {_.isString(message.content) ? (
                  <MessagePanelPart
                    value={message.content}
                    isStructuredOutput={isStructuredOutput}
                  />
                ) : (
                  message.content.map((p, i) => (
                    <MessagePanelPart key={i} value={p} />
                  ))
                )}
              </div>
            )}
            {message.tool_calls && (
              <div>
                <ToolCalls toolCalls={message.tool_calls} />
              </div>
            )}
          </div>

          {isOverflowing && (
            <ShowMoreButton
              isShowingMore={isShowingMore}
              setIsShowingMore={setIsShowingMore}
            />
          )}
        </div>
      </div>
    </div>
  );
};
