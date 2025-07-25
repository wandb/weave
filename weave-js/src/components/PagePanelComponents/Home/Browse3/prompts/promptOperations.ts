import {Messages} from '../pages/ChatView/types';
import {UseObjCreateParams} from '../pages/wfReactInterface/wfDataModelHooksInterface';

export interface CreateNewPromptOptions {
  projectId: string;
  entity: string;
  project: string;
  promptName: string;
  messages: Messages;
  objCreate: (useObjCreateParams: UseObjCreateParams) => Promise<any>;
  router: any;
}

export const createNewPrompt = async ({
  projectId,
  entity,
  project,
  promptName,
  messages,
  objCreate,
  router,
}: CreateNewPromptOptions): Promise<{
  url: string;
  objectId: string;
  objectDigest: string;
}> => {
  const newPromptResp = await objCreate({
    projectId,
    objectId: promptName,
    val: {
      _type: 'MessagesPrompt',
      name: promptName,
      description: null,
      _class_name: 'MessagesPrompt',
      _bases: ['Prompt', 'Object', 'BaseModel'],
      messages,
    },
  });

  const newPromptUrl = router.objectVersionUIUrl(
    entity,
    project,
    promptName,
    newPromptResp,
    undefined,
    undefined
  );

  return {
    url: newPromptUrl,
    objectId: promptName,
    objectDigest: newPromptResp,
  };
};
