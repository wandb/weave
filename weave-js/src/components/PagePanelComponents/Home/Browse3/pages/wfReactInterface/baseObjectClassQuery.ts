import {useDeepMemo} from '@wandb/weave/hookUtils';
import {useEffect, useRef, useState} from 'react';
import {z} from 'zod';

import {baseObjectClassRegistry} from './generatedBaseObjectClasses.zod';
import {TraceServerClient} from './traceServerClient';
import {useGetTraceServerClientContext} from './traceServerClientContext';
import {
  TraceObjCreateReq,
  TraceObjCreateRes,
  TraceObjQueryReq,
  TraceObjSchema,
} from './traceServerClientTypes';
import {Loadable} from './wfDataModelHooksInterface';

type ObjectClassRegistry = typeof baseObjectClassRegistry;  // TODO: Add more here - not just bases!
type ObjectClassRegistryKeys = keyof ObjectClassRegistry;
type ObjectClassType<C extends ObjectClassRegistryKeys> = z.infer<
  ObjectClassRegistry[C]
>;

export type TraceObjSchemaForObjectClass<
  C extends ObjectClassRegistryKeys
> = TraceObjSchema<ObjectClassType<C>, C>;

export const useBaseObjectInstances = <C extends ObjectClassRegistryKeys>(
  baseObjectClassName: C,
  req: TraceObjQueryReq
): Loadable<Array<TraceObjSchemaForObjectClass<C>>> => {
  const [objects, setObjects] = useState<
    Array<TraceObjSchemaForObjectClass<C>>
  >([]);
  const getTsClient = useGetTraceServerClientContext();
  const client = getTsClient();
  const deepReq = useDeepMemo(req);
  const currReq = useRef(deepReq);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    currReq.current = deepReq;
    getBaseObjectInstances(client, baseObjectClassName, deepReq).then(
      collectionObjects => {
        if (isMounted && currReq.current === deepReq) {
          setObjects(collectionObjects);
          setLoading(false);
        }
      }
    );
    return () => {
      isMounted = false;
    };
  }, [client, baseObjectClassName, deepReq]);

  return {result: objects, loading};
};

const getBaseObjectInstances = async <C extends ObjectClassRegistryKeys>(
  client: TraceServerClient,
  baseObjectClassName: C,
  req: TraceObjQueryReq
): Promise<Array<TraceObjSchema<ObjectClassType<C>, C>>> => {
  const knownObjectClass = baseObjectClassRegistry[baseObjectClassName];
  if (!knownObjectClass) {
    console.warn(`Unknown object class: ${baseObjectClassName}`);
    return [];
  }

  const reqWithBaseObjectClass: TraceObjQueryReq = {
    ...req,
    filter: {...req.filter, base_object_classes: [baseObjectClassName]},
  };

  const objectPromise = client.objsQuery(reqWithBaseObjectClass);

  const objects = await objectPromise;

  // We would expect that this  filtering does not filter anything
  // out because the backend enforces the base object class, but this
  // is here as a sanity check.
  return objects.objs
    .map(obj => ({obj, parsed: knownObjectClass.safeParse(obj.val)}))
    .filter(({parsed}) => parsed.success)
    .filter(({obj}) => obj.base_object_class === baseObjectClassName)
    .map(
      ({obj, parsed}) =>
        ({...obj, val: parsed.data} as TraceObjSchema<
          ObjectClassType<C>,
          C
        >)
    );
};

export const useCreateLeafObjectInstance = <
  C extends ObjectClassRegistryKeys,
  T = ObjectClassType<C>
>(
  leafObjectClassName: C
): ((req: TraceObjCreateReq<T>) => Promise<TraceObjCreateRes>) => {
  const getTsClient = useGetTraceServerClientContext();
  const client = getTsClient();
  return (req: TraceObjCreateReq<T>) =>
    createLeafObjectInstance(client, leafObjectClassName, req);
};

export const createLeafObjectInstance = async <
  C extends ObjectClassRegistryKeys, 
  T = ObjectClassType<C>
>(
  client: TraceServerClient,
  leafObjectClassName: C,
  req: TraceObjCreateReq<T>
): Promise<TraceObjCreateRes> => {
  if (
    req.obj.set_leaf_object_class != null &&
    req.obj.set_leaf_object_class !== leafObjectClassName
  ) {
    throw new Error(
      `set_leaf_object_class must match leafObjectClassName: ${leafObjectClassName}`
    );
  }

  const knownObjectClass = baseObjectClassRegistry[leafObjectClassName];
  if (!knownObjectClass) {
    throw new Error(`Unknown object class: ${leafObjectClassName}`);
  }

  const verifiedObject = knownObjectClass.safeParse(req.obj.val);

  if (!verifiedObject.success) {
    throw new Error(
      `Invalid object: ${JSON.stringify(verifiedObject.error.errors)}`
    );
  }

  const reqWithLeafObjectClass: TraceObjCreateReq = {
    ...req,
    obj: {
      ...req.obj,
      set_leaf_object_class: leafObjectClassName,
    },
  };

  return client.objCreate(reqWithLeafObjectClass);
};
