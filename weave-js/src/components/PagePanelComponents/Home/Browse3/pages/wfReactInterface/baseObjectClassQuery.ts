import {useDeepMemo} from '@wandb/weave/hookUtils';
import {useEffect, useRef, useState} from 'react';
import {z} from 'zod';

import {
  TestOnlyExampleSchema,
  TestOnlyNestedBaseObjectSchema,
} from './generatedBaseObjectClasses.zod';
import {TraceServerClient} from './traceServerClient';
import {useGetTraceServerClientContext} from './traceServerClientContext';
import {
  TraceObjCreateReq,
  TraceObjCreateRes,
  TraceObjQueryReq,
  TraceObjSchema,
} from './traceServerClientTypes';
import {Loadable} from './wfDataModelHooksInterface';

// TODO: This should be generated from the registry!
const baseObjectClassRegistry = {
  TestOnlyExample: TestOnlyExampleSchema,
  TestOnlyNestedBaseObject: TestOnlyNestedBaseObjectSchema,
};

export const useBaseObjectInstances = <
  C extends keyof typeof baseObjectClassRegistry,
  T = z.infer<(typeof baseObjectClassRegistry)[C]>
>(
  baseObjectClassName: C,
  req: TraceObjQueryReq
): Loadable<Array<TraceObjSchema<T, C>>> => {
  const [objects, setObjects] = useState<Array<TraceObjSchema<T, C>>>([]);
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
          setObjects(collectionObjects as Array<TraceObjSchema<T, C>>);
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

const getBaseObjectInstances = async <
  C extends keyof typeof baseObjectClassRegistry,
  T = z.infer<(typeof baseObjectClassRegistry)[C]>
>(
  client: TraceServerClient,
  baseObjectClassName: C,
  req: TraceObjQueryReq
): Promise<Array<TraceObjSchema<T, C>>> => {
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

  return objects.objs
    .map(obj => ({obj, parsed: knownObjectClass.safeParse(obj.val)}))
    .filter(({parsed}) => parsed.success)
    .map(({obj, parsed}) => ({...obj, val: parsed.data!})) as Array<
    TraceObjSchema<T, C>
  >;
};

export const useCreateBaseObjectInstance = <
  C extends keyof typeof baseObjectClassRegistry,
  T = z.infer<(typeof baseObjectClassRegistry)[C]>
>(
  baseObjectClassName: C
): ((req: TraceObjCreateReq<T>) => Promise<TraceObjCreateRes>) => {
  const getTsClient = useGetTraceServerClientContext();
  const client = getTsClient();
  return (req: TraceObjCreateReq<T>) =>
    createBaseObjectInstance(client, baseObjectClassName, req);
};

const createBaseObjectInstance = async <
  C extends keyof typeof baseObjectClassRegistry,
  T = z.infer<(typeof baseObjectClassRegistry)[C]>
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
