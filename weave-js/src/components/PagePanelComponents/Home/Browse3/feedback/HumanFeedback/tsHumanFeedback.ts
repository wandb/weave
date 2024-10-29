import {useEffect, useMemo, useState} from 'react';

import {useWFHooks} from '../../pages/wfReactInterface/context';
import {objectVersionKeyToRefUri} from '../../pages/wfReactInterface/utilities';
import {ObjectVersionSchema} from '../../pages/wfReactInterface/wfDataModelHooksInterface';
import {tsHumanFeedbackColumn} from './humanFeedbackTypes';


// const useResolveTypeObjects = (typeRefs: string[]) => {
//   const {useRefsData} = useWFHooks();
//   const refsData = useRefsData(typeRefs);
//   return useMemo(() => {
//     if (refsData.loading || refsData.result == null) {
//       return null;
//     }
//     const refDataWithRefs = refsData.result.map((x, i) => ({
//       ...x,
//       ref: typeRefs[i],
//     }));
//     return refDataWithRefs;
//   }, [refsData.loading, refsData.result]);
// };


export const useHumanFeedbackOptions = (
  entity: string,
  project: string
): tsHumanFeedbackColumn[] => {
  const {useRootObjectVersions} = useWFHooks();

  const [cols, setCols] = useState<ObjectVersionSchema[] | null>(
    null
  );
  const humanAnnotationColumns = useRootObjectVersions(
    entity,
    project,
    {
      baseObjectClasses: ['HumanAnnotationColumn'],
      latestOnly: true,
    },
    undefined, // limit
    false // metadataOnly
  );

  useEffect(() => {
    if (humanAnnotationColumns.loading || humanAnnotationColumns.result == null) {
      return;
    }
    setCols(humanAnnotationColumns.result);
  }, [humanAnnotationColumns.loading, humanAnnotationColumns.result]);

  return useMemo(() => {
    if (cols == null) {
      return [];
    }
    return cols.map((col) => ({
      ...col.val,
      ref: objectVersionKeyToRefUri(col),
    }));
  }, [cols]);
};
