/**
 * This file contains the utilities that relate to working with the wfReactInterface and are
 * intended to be consumed by external callers (ie. important from outside this module).
 */

import { useWFHooks } from "./context";
import { CallSchema, Loadable } from "./interface";

export const useParentCall = (
    call: CallSchema | null
  ): Loadable<CallSchema | null> => {
    const {useCall} = useWFHooks();
    let parentCall = null;
    if (call && call.parentId) {
      parentCall = {
        entity: call.entity,
        project: call.project,
        callId: call.parentId,
      };
    }
    return useCall(parentCall);
  };
