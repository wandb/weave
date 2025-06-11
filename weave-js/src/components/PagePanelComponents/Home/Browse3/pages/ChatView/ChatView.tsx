import {Callout} from '@wandb/weave/components/Callout';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import React, {useEffect, useMemo, useRef} from 'react';

import {useDeepMemo} from '../../../../../../hookUtils';
import {usePlaygroundContext} from '../PlaygroundPage/PlaygroundContext';
import {ChoicesView} from './ChoicesView';
import {MessageList} from './MessageList';
import {MessagePanel} from './MessagePanel';
import {Chat} from './types';

type ChatViewProps = {
  chat: Chat;
};

export const ChatView = ({chat}: ChatViewProps) => {
  const outputRef = useRef<HTMLDivElement>(null);
  const playgroundContext = usePlaygroundContext();

  const chatResult = useDeepMemo(chat.result);

  // Check if we should show loading state
  const shouldShowLoading = useMemo(() => {
    if (!playgroundContext.isPlayground) {
      return false;
    }

    const messages = chat.request?.messages || [];
    if (messages.length === 0) {
      return false;
    }

    // Check if the last message is from user and we have no result yet
    const lastMessage = messages[messages.length - 1];
    const isLastMessageFromUser = lastMessage.role === 'user';

    return isLastMessageFromUser && !chatResult;
  }, [playgroundContext.isPlayground, chat.request?.messages, chatResult]);

  const scrollLastMessage = useMemo(
    () =>
      !(
        outputRef.current &&
        chatResult &&
        'choices' in chatResult &&
        chatResult.choices
      ),
    [chatResult]
  );

  useEffect(() => {
    if (
      outputRef.current &&
      chatResult &&
      'choices' in chatResult &&
      chatResult.choices
    ) {
      outputRef.current.scrollIntoView();
    }
  }, [chatResult]);

  return (
    <div className="flex flex-col pb-32">
      <p className="mb-[8px] text-sm font-semibold text-moon-800">Messages</p>
      <MessageList
        messages={chat.request?.messages || []}
        scrollLastMessage={scrollLastMessage}
      />
      {/* Show loading state when waiting for response */}
      {shouldShowLoading && (
        <>
          <span className="mb-[8px] text-sm font-semibold text-moon-800">
            Response
          </span>
          <div className="flex gap-[16px] py-4">
            <div className="w-32 flex-shrink-0">
              <Callout
                size="x-small"
                icon="robot-service-member"
                color="moon"
                className="mt-[4px] h-32 w-32 bg-moon-100"
              />
            </div>
            <div className="flex items-center">
              <WaveLoader size="small" />
            </div>
          </div>
        </>
      )}
      {chatResult &&
        'content' in chatResult &&
        chatResult.content &&
        chatResult.content.length > 0 && (
          <>
            <span className="mb-[8px] text-sm font-semibold text-moon-800">
              Response
            </span>
            <div ref={outputRef}>
              <MessagePanel
                index={0}
                message={chatResult}
                isStructuredOutput={chat.isStructuredOutput}
                isNested={false}
                choiceIndex={0}
                messageHeader={null}
              />
            </div>
          </>
        )}
      {chatResult &&
        'choices' in chatResult &&
        chatResult.choices &&
        chatResult.choices.length > 0 && (
          <>
            <span className="mb-[8px] text-sm font-semibold text-moon-800">
              Response
            </span>
            <div ref={outputRef}>
              <ChoicesView
                isStructuredOutput={chat.isStructuredOutput}
                choices={chatResult.choices}
              />
            </div>
          </>
        )}
    </div>
  );
};
