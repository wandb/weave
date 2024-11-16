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

type BaseObjectClassRegistry = typeof baseObjectClassRegistry;
type BaseObjectClassRegistryKeys = keyof BaseObjectClassRegistry;
type BaseObjectClassType<C extends BaseObjectClassRegistryKeys> = z.infer<
  BaseObjectClassRegistry[C]
>;

export type TraceObjSchemaForBaseObjectClass<
  C extends BaseObjectClassRegistryKeys
> = TraceObjSchema<BaseObjectClassType<C>, C>;

export const useBaseObjectInstances = <C extends BaseObjectClassRegistryKeys>(
  baseObjectClassName: C,
  req: TraceObjQueryReq
): Loadable<Array<TraceObjSchemaForBaseObjectClass<C>>> => {
  const [objects, setObjects] = useState<
    Array<TraceObjSchemaForBaseObjectClass<C>>
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

const getBaseObjectInstances = async <C extends BaseObjectClassRegistryKeys>(
  client: TraceServerClient,
  baseObjectClassName: C,
  req: TraceObjQueryReq
): Promise<Array<TraceObjSchema<BaseObjectClassType<C>, C>>> => {
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
          BaseObjectClassType<C>,
          C
        >)
    );
};

export const useCreateBaseObjectInstance = <
  C extends BaseObjectClassRegistryKeys,
  T = BaseObjectClassType<C>
>(
  baseObjectClassName: C
): ((req: TraceObjCreateReq<T>) => Promise<TraceObjCreateRes>) => {
  const getTsClient = useGetTraceServerClientContext();
  const client = getTsClient();
  return (req: TraceObjCreateReq<T>) =>
    createBaseObjectInstance(client, baseObjectClassName, req);
};

export const createBaseObjectInstance = async <
  C extends BaseObjectClassRegistryKeys,
  T = BaseObjectClassType<C>
>(
  client: TraceServerClient,
  baseObjectClassName: C,
  req: TraceObjCreateReq<T>
): Promise<TraceObjCreateRes> => {
  if (
    req.obj.set_base_object_class != null &&
    req.obj.set_base_object_class !== baseObjectClassName
  ) {
    throw new Error(
      `set_base_object_class must match baseObjectClassName: ${baseObjectClassName}`
    );
  }

  const knownBaseObjectClass = baseObjectClassRegistry[baseObjectClassName];
  if (!knownBaseObjectClass) {
    throw new Error(`Unknown object class: ${baseObjectClassName}`);
  }

  const verifiedObject = knownBaseObjectClass.safeParse(req.obj.val);

  if (!verifiedObject.success) {
    throw new Error(
      `Invalid object: ${JSON.stringify(verifiedObject.error.errors)}`
    );
  }

  const reqWithBaseObjectClass: TraceObjCreateReq = {
    ...req,
    obj: {
      ...req.obj,
      set_base_object_class: baseObjectClassName,
    },
  };

  return client.objCreate(reqWithBaseObjectClass);
};
