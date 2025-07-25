import {useCallback, useState} from 'react';
import {useHistory} from 'react-router-dom';
import {toast} from 'react-toastify';

import {
  useWeaveflowCurrentRouteContext,
  useWeaveflowRouteContext,
} from '../context';
import {Messages} from '../pages/ChatView/types';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {createNewPrompt} from './promptOperations';

interface UsePromptSavingOptions {
  entity: string;
  project: string;
  onSaveComplete?: (promptRef?: string) => void;
}

interface PromptSavingResult {
  isCreatingPrompt: boolean;
  handleSavePrompt: (name: string, messages: Messages) => Promise<void>;
}

/**
 * Hook for saving prompts that encapsulates the common logic used in multiple places.
 */
export const usePromptSaving = ({
  entity,
  project,
  onSaveComplete,
}: UsePromptSavingOptions): PromptSavingResult => {
  const {peekingRouter} = useWeaveflowRouteContext();
  const history = useHistory();
  const [isCreatingPrompt, setisCreatingPrompt] = useState(false);
  const router = useWeaveflowCurrentRouteContext();
  const {useObjCreate} = useWFHooks();

  // Get the create hooks
  const objCreate = useObjCreate();

  const handleSavePrompt = useCallback(
    async (name: string, messages: Messages) => {
      setisCreatingPrompt(true);
      let promptRef: undefined | string = undefined;
      try {
        // Create the prompt using the actual API function
        const result = await createNewPrompt({
          projectId: `${entity}/${project}`,
          entity,
          project,
          promptName: name,
          messages,
          objCreate,
          router,
        });

        // Note: This is different behavior than dataset creation,
        // where we show a toast with a link to the new dataset.
        const to = peekingRouter.objectVersionUIUrl(
          entity,
          project,
          name,
          result.objectDigest
        );
        history.push(to);
      } catch (error: any) {
        console.error('Failed to create prompt:', error);
        toast.error(`Failed to create prompt: ${error.message}`);
      } finally {
        setisCreatingPrompt(false);
        onSaveComplete?.(promptRef);
      }
    },
    [entity, project, objCreate, router, onSaveComplete, history, peekingRouter]
  );

  return {
    isCreatingPrompt,
    handleSavePrompt,
  };
};
