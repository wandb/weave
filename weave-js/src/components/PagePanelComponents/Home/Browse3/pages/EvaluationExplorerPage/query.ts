import {makeRefObject} from '@wandb/weave/util/refs';

import {TraceServerClient} from '../wfReactInterface/traceServerClient';

const makeSafe = <T>(
  fn: (...args: any[]) => Promise<T>,
  defaultValue: T,
  errorMessage?: (e: any) => string
) => {
  return async (...args: any[]) => {
    try {
      return await fn(...args);
    } catch (e: any) {
      console.error(errorMessage ? errorMessage(e) : e);
      return defaultValue;
    }
  };
};

export const getLatestEvaluationRefs = async (
  client: TraceServerClient,
  entity: string,
  project: string
): Promise<string[]> => {
  const res = await client.objsQuery({
    project_id: `${entity}/${project}`,
    filter: {
      base_object_classes: ['Evaluation'],
      latest_only: true,
    },
    // TODO: Add pagination or smarter filtering.
    limit: 1000,
    metadata_only: true,
  });
  return res.objs.map(o =>
    makeRefObject(entity, project, 'object', o.object_id, o.digest, undefined)
  );
};

// export const getLatestEvaluationRefsSafe = makeSafe(
//   getLatestEvaluationRefs,
//   []
// );
