import { useEffect, useMemo, useState } from "react";
import { useWFHooks } from "../../pages/wfReactInterface/context";
import { objectVersionKeyToRefUri } from "../../pages/wfReactInterface/utilities";
import { ObjectVersionSchema } from "../../pages/wfReactInterface/wfDataModelHooksInterface";

// const useResolveTypeObjects = (typeRefs: string[]) => {
//     const {useRefsData} = useWFHooks();
//     const refsData = useRefsData(typeRefs);
//     return useMemo(() => {
//       if (refsData.loading || refsData.result == null) {
//         return null;
//       }
//       const refDataWithRefs = refsData.result.map((x, i) => ({
//         ...x,
//         ref: typeRefs[i],
//       }));
//       return refDataWithRefs;
//     }, [refsData.loading, refsData.result]);
//   };
  
  export const useStructuredFeedbackOptions = (entity: string, project: string) => {
    const {useRootObjectVersions} = useWFHooks();
  
    const [latestSpec, setLatestSpec] = useState<ObjectVersionSchema | null>(null);
    const structuredFeedbackObjects = useRootObjectVersions(
      entity,
      project,
      {
        baseObjectClasses: ['StructuredFeedback'],
        latestOnly: true,
      },
      undefined,
    );
    // const refsData = useResolveTypeObjects(latestSpec?.val.types ?? []);
    const refsData = latestSpec?.val.types;
  
    useEffect(() => {
      if (structuredFeedbackObjects.loading || structuredFeedbackObjects.result == null) {
        return;
      }
      const latestSpec = structuredFeedbackObjects.result?.sort((a, b) => a.createdAtMs - b.createdAtMs).pop();
      if (!latestSpec) {
        return;
      }
      setLatestSpec(latestSpec);
    }, [structuredFeedbackObjects.loading, structuredFeedbackObjects.result]);
  
    return useMemo(() => {
      if (latestSpec == null || refsData == null) {
        return null;
      }
      return {
        types: refsData,
        ref: objectVersionKeyToRefUri(latestSpec),
      };
    }, [latestSpec, refsData]);
  };
  