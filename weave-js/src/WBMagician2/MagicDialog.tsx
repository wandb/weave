import React, {useEffect} from 'react';

import {EntityProject, useChatCompletion} from './chatCompletionClient';

type MagicFillProps = {
  entityProject?: EntityProject;
  open: boolean;
  onClose: () => void;
  onAccept: (newContent: string) => void;
  // Modal title and details
  title: string;
  details: string;
  // Hidden system prompt
  systemPrompt: string;
  // Original content to revise (optional)
  contentToRevise?: string;
  // Placeholder for user input collection
  userInstructionPlaceholder: string;
};

/**
 * MagicFill is a dialog component that helps the user fill in a form.
 * It uses the `useChatCompletion` hook to invoke an LLM.
 */
export const MagicFill: React.FC<MagicFillProps> = props => {
  const chatCompletion = useChatCompletion(props.entityProject);
  // TODO: implement the dialog
  useEffect(() => {
    console.log(
      'MagicFill',
      chatCompletion({
        modelId: 'gpt-4o-mini',
        messages: 'test',
      })
    );
  }, [chatCompletion]);
};
