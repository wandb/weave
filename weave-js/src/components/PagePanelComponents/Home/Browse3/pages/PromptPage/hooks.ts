import {useMemo} from 'react';

import {useWFHooks} from '../wfReactInterface/context';

export const usePrompt = (entity: string, project: string, data: any) => {
  const {useFileContent} = useWFHooks();
  const promptJson = useFileContent(
    entity,
    project,
    data.messages.files['obj.json']
  );

  const result = useMemo(() => {
    if (promptJson.loading) {
      return {
        loading: true,
        prompt: null,
      };
    }
    if (promptJson.result == null) {
      return {
        loading: false,
        prompt: null,
      };
    }
    const messages = JSON.parse(new TextDecoder().decode(promptJson.result));
    // TODO: Properly recreate placeholders from message
    const prompt = {
      messages,
      placeholders: [],
    };
    return {
      loading: false,
      prompt,
    };
  }, [promptJson]);
  return result;
};
