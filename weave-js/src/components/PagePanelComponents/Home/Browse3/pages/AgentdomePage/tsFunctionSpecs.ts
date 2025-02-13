import {useEffect, useMemo, useRef, useState} from 'react';

import {FunctionSpec} from '../wfReactInterface/generatedBuiltinObjectClasses.zod';
import {
  useBaseObjectInstances,
  useCreateBuiltinObjectInstance,
} from '../wfReactInterface/objectClassQuery';
import {
  TraceObjQueryReq,
  TraceObjSchema,
} from '../wfReactInterface/traceServerClientTypes';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';

export const useFunctionSpecs = (
  entity: string,
  project: string
): {functionSpecs: FunctionSpec[]; specsLoading: boolean} => {
  const req: TraceObjQueryReq = {
    project_id: projectIdFromParts({entity, project}),
  };
  const res = useBaseObjectInstances('FunctionSpec', req);
  const [cols, setCols] = useState<TraceObjSchema[] | null>(null);

  const loading = useRef(true);

  useEffect(() => {
    if (res.loading || res.result == null) {
      return;
    }
    if (loading.current) {
      loading.current = false;
      setCols(res.result);
    }
  }, [res.loading, res.result]);

  return useMemo(() => {
    if (cols == null) {
      return {functionSpecs: [], specsLoading: loading.current};
    }
    return {
      functionSpecs: cols.map(col => col.val),
      specsLoading: loading.current,
    };
  }, [cols]);
};

export const useMakeFunctionSpec = () => {
  const createFunctionSpec = useCreateBuiltinObjectInstance('FunctionSpec');
  return createFunctionSpec;
};
