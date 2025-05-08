import {Button} from '@wandb/weave/components/Button';
import React, {useState} from 'react';

import {StyledTextArea} from '../../../StyledTextarea';
import {PlaygroundMessageRole} from '../types';

type PlaygroundChatInputProps = {
  chatText: string;
  setChatText: (text: string) => void;
  isLoading: boolean;
  onSend: (role: PlaygroundMessageRole, chatText: string) => void;
  onAdd: (role: PlaygroundMessageRole, chatText: string) => void;
  settingsTab: number | null;
  hasConfiguredProviders?: boolean;
};

const isMac = () => {
  const platform = navigator.platform || '';
  const userAgent = navigator.userAgent || '';
  const appVersion = navigator.appVersion || '';
  const checkString = (str: string) => /Mac|iPhone|iPod|iPad/i.test(str);
  return (
    checkString(platform) || checkString(userAgent) || checkString(appVersion)
  );
};

export const PlaygroundChatInput: React.FC<PlaygroundChatInputProps> = ({
  chatText,
  setChatText,
  isLoading,
  onSend,
  onAdd,
  hasConfiguredProviders = true,
}) => {
  const [addMessageRole, setAddMessageRole] =
    useState<PlaygroundMessageRole>('user');
  const [shouldReset, setShouldReset] = useState(false);

  const handleReset = () => {
    setShouldReset(true);
    setTimeout(() => setShouldReset(false), 0);
  };

  const handleSend = (role: PlaygroundMessageRole) => {
    onSend(role, chatText);
    handleReset();
  };

  const handleAdd = (role: PlaygroundMessageRole, text: string) => {
    onAdd(role, text);
    handleReset();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      handleSend(addMessageRole);
    }
  };

  return (
    // WARN: z-index position of navbar overflow menu is `2`, check first if changing
    <div className="z-1 flex min-h-[160px] w-full flex-shrink-0 bg-white p-16 pt-8">
      <div className="mx-auto w-full max-w-[800px]">
        <div className="mb-8 text-right text-xs text-moon-500">
          Press {isMac() ? 'CMD' : 'Ctrl'} + Enter to send
        </div>
        <StyledTextArea
          onChange={e => setChatText(e.target.value)}
          value={chatText}
          onKeyDown={handleKeyDown}
          placeholder={
            hasConfiguredProviders
              ? 'Type your message here...'
              : 'Configure a provider to start chatting...'
          }
          autoGrow
          maxHeight={160}
          reset={shouldReset}
          disabled={!hasConfiguredProviders}
        />
        <div className="flex justify-between">
          <div className="flex gap-8">
            {/* TODO: Add image upload */}
            {/* <Button variant="secondary" size="small" startIcon="photo" /> */}
          </div>
          <div className="flex gap-8">
            <div className="flex items-center text-xs text-moon-500">
              Add as
              <Button
                className="ml-4 rounded-r-none"
                variant="secondary"
                size="medium"
                active={addMessageRole === 'system'}
                onClick={() => setAddMessageRole('system')}>
                System
              </Button>
              <Button
                className="rounded-none"
                variant="secondary"
                size="medium"
                active={addMessageRole === 'assistant'}
                onClick={() => setAddMessageRole('assistant')}>
                Assistant
              </Button>
              <Button
                className="rounded-l-none"
                variant="secondary"
                size="medium"
                active={addMessageRole === 'user'}
                onClick={() => setAddMessageRole('user')}>
                User
              </Button>
            </div>
            <Button
              variant="secondary"
              size="medium"
              startIcon="add-new"
              disabled={
                isLoading || chatText.trim() === '' || !hasConfiguredProviders
              }
              onClick={() => handleAdd(addMessageRole, chatText)}>
              Add
            </Button>
            <div className="h-full w-px bg-moon-250" />
            <Button
              size="medium"
              onClick={() => handleSend(addMessageRole)}
              disabled={
                isLoading || chatText.trim() === '' || !hasConfiguredProviders
              }
              startIcon={isLoading ? 'loading' : undefined}>
              {isLoading ? 'Sending...' : 'Send'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
