import {useEffect, useMemo, useState} from 'react';

import {useBaseObjectInstances} from '../../pages/wfReactInterface/objectClassQuery';
import {
  TraceObjQueryReq,
  TraceObjSchema,
} from '../../pages/wfReactInterface/traceServerClientTypes';
import {projectIdFromParts} from '../../pages/wfReactInterface/tsDataModelHooks';
import {objectVersionKeyToRefUri} from '../../pages/wfReactInterface/utilities';
import {tsHumanAnnotationSpec} from './humanAnnotationTypes';

export const useHumanAnnotationSpecs = (
  entity: string,
  project: string
): {humanAnnotationSpecs: tsHumanAnnotationSpec[]; specsLoading: boolean} => {
  const req: TraceObjQueryReq = {
    project_id: projectIdFromParts({entity, project}),
    filter: {
      latest_only: true,
    },
  };
  const res = useBaseObjectInstances('AnnotationSpec', req);
  const [cols, setCols] = useState<TraceObjSchema[] | null>(null);

  useEffect(() => {
    if (res.loading || res.result == null) {
      return;
    }
    setCols(res.result);
  }, [res.loading, res.result]);

  return useMemo(() => {
    if (cols == null) {
      return {humanAnnotationSpecs: [], specsLoading: res.loading};
    }
    return {
      humanAnnotationSpecs: cols.map(col => ({
        ...col.val,
        // attach object refs to the columns
        ref: objectVersionKeyToRefUri({
          scheme: 'weave',
          weaveKind: 'object',
          entity,
          project,
          objectId: col.object_id,
          versionHash: col.digest,
          path: '',
        }),
      })),
      specsLoading: res.loading,
    };
  }, [cols, entity, project, res.loading]);
};
