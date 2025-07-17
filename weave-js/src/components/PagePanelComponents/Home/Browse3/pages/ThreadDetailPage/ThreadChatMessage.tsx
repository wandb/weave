import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import React, {FC} from 'react';

import {ChatView} from '../ChatView/ChatView';
import {useCallAsChat} from '../ChatView/hooks';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';

interface ThreadChatMessageProps {
  call: TraceCallSchema;
}
export const ThreadChatMessage: FC<ThreadChatMessageProps> = ({
  call,
}: ThreadChatMessageProps) => {
  const chat = useCallAsChat(call);

  if (chat.loading) {
    return (
      <div className="flex w-full items-center justify-center">
        <LoadingDots />
      </div>
    );
  }

  return <ChatView chat={chat} showTitle={false} />;
};
