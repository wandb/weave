import {makeRefObject} from '@wandb/weave/util/refs';

import {TraceServerClient} from '../wfReactInterface/traceServerClient';

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
