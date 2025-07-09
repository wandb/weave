import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import React, {FC} from 'react';

import {ChatView} from '../ChatView/ChatView';
import {useCallAsChat} from '../ChatView/hooks';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';

export interface CallChatProps {
  call: TraceCallSchema;
  showTitle?: boolean;
}

/**
 * CallChat renders a single TraceCallSchema as a chat interface.
 *
 * Converts the call to Chat format using existing normalization logic
 * and renders it with the standard ChatView component.
 *
 * @param call - The trace call to render as chat
 * @param showTitle - Whether to show section titles
 *
 * @example
 * <CallChat call={traceCall} showTitle={true} />
 */
export const CallChat: FC<CallChatProps> = ({call, showTitle = false}) => {
  // Use existing chat conversion logic
  const chatData = useCallAsChat(call);

  if (chatData.loading) {
    return (
      <div className="flex w-full items-center justify-center">
        <LoadingDots />
      </div>
    );
  }

  // Don't render if this call doesn't have chat format
  if (!chatData.request || !chatData.request.messages) {
    return null;
  }

  return <ChatView chat={chatData} showTitle={showTitle} />;
};
