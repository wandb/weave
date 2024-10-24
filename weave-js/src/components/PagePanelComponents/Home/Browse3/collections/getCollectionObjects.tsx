import {useDeepMemo} from '@wandb/weave/hookUtils';
import {useEffect, useState} from 'react';
import {z} from 'zod';

import {TraceServerClient} from '../pages/wfReactInterface/traceServerClient';
import {useGetTraceServerClientContext} from '../pages/wfReactInterface/traceServerClientContext';
import {
  TraceObjCreateReq,
  TraceObjQueryReq,
  TraceObjSchema,
} from '../pages/wfReactInterface/traceServerClientTypes';
import {collectionRegistry} from './collectionRegistry';

export const useCollectionObjects = <
  C extends keyof typeof collectionRegistry,
  T extends z.infer<(typeof collectionRegistry)[C]>
>(
  collectionName: C,
  req: TraceObjQueryReq
) => {
  const [objects, setObjects] = useState<Array<TraceObjSchema<T>>>([]);
  const getTsClient = useGetTraceServerClientContext();
  const client = getTsClient();
  const deepReq = useDeepMemo(req);

  useEffect(() => {
    let isMounted = true;
    getCollectionObjects(client, collectionName, deepReq).then(
      collectionObjects => {
        if (isMounted) {
          setObjects(collectionObjects as Array<TraceObjSchema<T>>);
        }
      }
    );
    return () => {
      isMounted = false;
    };
  }, [client, collectionName, deepReq]);

  return objects;
};

const getCollectionObjects = async <
  C extends keyof typeof collectionRegistry,
  T extends z.infer<(typeof collectionRegistry)[C]>
>(
  client: TraceServerClient,
  collectionName: C,
  req: TraceObjQueryReq
): Promise<Array<TraceObjSchema<T>>> => {
  const knownCollection = collectionRegistry[collectionName];
  if (!knownCollection) {
    console.warn(`Unknown collection: ${collectionName}`);
    return [];
  }

  const reqWithCollection: TraceObjQueryReq = {
    ...req,
    filter: {...req.filter, base_object_classes: [collectionName]},
  };

  const objectPromise = client.objsQuery(reqWithCollection);

  const objects = await objectPromise;

  return objects.objs
    .map(obj => ({obj, parsed: knownCollection.safeParse(obj.val)}))
    .filter(({parsed}) => parsed.success)
    .map(({obj, parsed}) => ({...obj, val: parsed.data!})) as Array<
    TraceObjSchema<T>
  >;
};

export const useCreateCollectionObject = <
  C extends keyof typeof collectionRegistry,
  T extends z.infer<(typeof collectionRegistry)[C]>
>(
  collectionName: C
) => {
  const getTsClient = useGetTraceServerClientContext();
  const client = getTsClient();
  return (req: TraceObjCreateReq<T>) =>
    createCollectionObject(client, collectionName, req);
};

const createCollectionObject = async <
  C extends keyof typeof collectionRegistry,
  T extends z.infer<(typeof collectionRegistry)[C]>
>(
  client: TraceServerClient,
  collectionName: C,
  req: TraceObjCreateReq<T>
) => {
  const knownCollection = collectionRegistry[collectionName];
  if (!knownCollection) {
    throw new Error(`Unknown collection: ${collectionName}`);
  }

  const verifiedObject = knownCollection.safeParse(req.obj.val);

  if (!verifiedObject.success) {
    throw new Error(
      `Invalid object: ${JSON.stringify(verifiedObject.error.errors)}`
    );
  }

  const reqWithCollection: TraceObjCreateReq = {
    ...req,
    obj: {
      ...req.obj,
      val: {...req.obj.val, _bases: [collectionName, 'BaseModel']},
    },
  };

  const createPromse = client.objCreate(reqWithCollection);

  return createPromse;
};
