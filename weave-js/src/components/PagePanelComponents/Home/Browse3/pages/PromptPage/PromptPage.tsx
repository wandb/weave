import React from 'react';
import {useWFHooks} from '../wfReactInterface/context';
import {LoadingDots} from '../../../../../LoadingDots';
import {MessageList} from './MessageList';
import {Tailwind} from '../../../../../Tailwind';

type Data = Record<string, any>;

type PromptPageProps = {
  entity: string;
  project: string;
  data: Data;
};

export const PromptPage = ({entity, project, data}: PromptPageProps) => {
  const {useFileContent} = useWFHooks();
  const promptJson = useFileContent(
    entity,
    project,
    data.messages.files['obj.json']
  );

  if (promptJson.loading) {
    return <LoadingDots />;
  } else if (promptJson.result == null) {
    return <span></span>;
  }

  const prompt = JSON.parse(new TextDecoder().decode(promptJson.result));
  console.log({prompt});
  return (
    <Tailwind>
      <MessageList messages={prompt.messages} />
    </Tailwind>
  );
};
