import {useDeepMemo} from '@wandb/weave/hookUtils';
import {useCallback, useEffect, useRef, useState} from 'react';
import {z} from 'zod';

import {builtinObjectClassRegistry} from './generatedBuiltinObjectClasses.zod';
import {TraceServerClient} from './traceServerClient';
import {useGetTraceServerClientContext} from './traceServerClientContext';
import {
  TraceObjCreateReq,
  TraceObjCreateRes,
  TraceObjQueryReq,
  TraceObjSchema,
} from './traceServerClientTypes';
import {LoadableWithError} from './wfDataModelHooksInterface';

/**
 * Object query hooks for base and leaf object classes.
 *
 * Usage examples:
 *
 * // Query by base object class (parent class):
 * const baseObjects = useBaseObjectInstances('Dataset', {
 *   project_id: 'my-project',
 *   limit: 10
 * });
 *
 * // Query by leaf object class (specific implementation):
 * const leafObjects = useLeafObjectInstances('Dataset', {
 *   project_id: 'my-project',
 *   limit: 10
 * });
 */

type BuiltinObjectClassRegistry = typeof builtinObjectClassRegistry;
type BuiltinObjectClassRegistryKeys = keyof BuiltinObjectClassRegistry;
type BaseObjectClassType<C extends BuiltinObjectClassRegistryKeys> = z.infer<
  BuiltinObjectClassRegistry[C]
>;

export type TraceObjSchemaForBaseObjectClass<
  C extends BuiltinObjectClassRegistryKeys
> = TraceObjSchema<BaseObjectClassType<C>, C>;

type BaseObjectInstancesState<C extends BuiltinObjectClassRegistryKeys> =
  LoadableWithError<Array<TraceObjSchemaForBaseObjectClass<C>>>;

type BaseObjectInstancesResult<C extends BuiltinObjectClassRegistryKeys> =
  BaseObjectInstancesState<C> & {
    refetch: () => void;
  };

// Types for leaf object instances
type LeafObjectInstancesState<C extends BuiltinObjectClassRegistryKeys> =
  LoadableWithError<Array<TraceObjSchemaForBaseObjectClass<C>>>;

type LeafObjectInstancesResult<C extends BuiltinObjectClassRegistryKeys> =
  LeafObjectInstancesState<C> & {
    refetch: () => void;
  };

// Notice: this is still `base` object class, not `builtin` object class.
// This means we can search by base object class, but not builtin object class today.
// See https://github.com/wandb/weave/pull/3229 for more details.
// base_object_class: this is the name of the first subclass of any subclass of a weave Object class.
// object_class: the string of the actual class.
export const useBaseObjectInstances = <
  C extends BuiltinObjectClassRegistryKeys
>(
  baseObjectClassName: C,
  req: TraceObjQueryReq
): BaseObjectInstancesResult<C> => {
  const getTsClient = useGetTraceServerClientContext();
  const client = getTsClient();
  const deepReq = useDeepMemo(req);
  const currReq = useRef(deepReq);
  const [result, setResult] = useState<BaseObjectInstancesState<C>>({
    loading: true,
    result: null,
    error: null,
  });
  const [doReload, setDoReload] = useState(false);
  const refetch = useCallback(() => {
    setDoReload(true);
  }, [setDoReload]);

  useEffect(() => {
    let isMounted = true;
    if (doReload) {
      setDoReload(false);
    }
    setResult({
      loading: true,
      result: null,
      error: null,
    });
    currReq.current = deepReq;
    getBaseObjectInstances(client, baseObjectClassName, deepReq)
      .then(collectionObjects => {
        if (isMounted && currReq.current === deepReq) {
          setResult({
            loading: false,
            result: collectionObjects,
            error: null,
          });
        }
      })
      .catch(error => {
        if (isMounted && currReq.current === deepReq) {
          setResult({
            loading: false,
            result: null,
            error,
          });
        }
      });
    return () => {
      isMounted = false;
    };
  }, [client, baseObjectClassName, deepReq, doReload]);

  return {...result, refetch};
};

const getBaseObjectInstances = async <C extends BuiltinObjectClassRegistryKeys>(
  client: TraceServerClient,
  baseObjectClassName: C,
  req: TraceObjQueryReq
): Promise<Array<TraceObjSchema<BaseObjectClassType<C>, C>>> => {
  const knownObjectClass = builtinObjectClassRegistry[baseObjectClassName];
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

  // We would expect that this filtering does not filter anything
  // out because the backend enforces the base object class, but this
  // is here as a sanity check.
  const filteredObjects = objects.objs
    .map(obj => ({obj, parsed: knownObjectClass.safeParse(obj.val)}))
    .map(({obj, parsed}) => {
      if (!parsed.success) {
        console.warn(
          `Failed to parse object: ${JSON.stringify(parsed.error.errors)}`
        );
      }
      return {obj, parsed};
    })
    .filter(({parsed}) => parsed.success)
    .filter(({obj}) => obj.base_object_class === baseObjectClassName)
    .map(
      ({obj, parsed}) =>
        ({...obj, val: parsed.data} as TraceObjSchema<
          BaseObjectClassType<C>,
          C
        >)
    );
  return filteredObjects;
};

// Hook for querying leaf object instances
// leaf_object_class: the actual string name of the specific class implementation
export const useLeafObjectInstances = <
  C extends BuiltinObjectClassRegistryKeys
>(
  leafObjectClassName: C,
  req: TraceObjQueryReq
): LeafObjectInstancesResult<C> => {
  const getTsClient = useGetTraceServerClientContext();
  const client = getTsClient();
  const deepReq = useDeepMemo(req);
  const currReq = useRef(deepReq);
  const [result, setResult] = useState<LeafObjectInstancesState<C>>({
    loading: true,
    result: null,
    error: null,
  });
  const [doReload, setDoReload] = useState(false);
  const refetch = useCallback(() => {
    setDoReload(true);
  }, [setDoReload]);

  useEffect(() => {
    let isMounted = true;
    if (doReload) {
      setDoReload(false);
    }
    setResult({
      loading: true,
      result: null,
      error: null,
    });
    currReq.current = deepReq;
    getLeafObjectInstances(client, leafObjectClassName, deepReq)
      .then(collectionObjects => {
        if (isMounted && currReq.current === deepReq) {
          setResult({
            loading: false,
            result: collectionObjects,
            error: null,
          });
        }
      })
      .catch(error => {
        if (isMounted && currReq.current === deepReq) {
          setResult({
            loading: false,
            result: null,
            error,
          });
        }
      });
    return () => {
      isMounted = false;
    };
  }, [client, leafObjectClassName, deepReq, doReload]);

  return {...result, refetch};
};

const getLeafObjectInstances = async <C extends BuiltinObjectClassRegistryKeys>(
  client: TraceServerClient,
  leafObjectClassName: C,
  req: TraceObjQueryReq
): Promise<Array<TraceObjSchema<BaseObjectClassType<C>, C>>> => {
  const knownObjectClass = builtinObjectClassRegistry[leafObjectClassName];
  if (!knownObjectClass) {
    console.warn(`Unknown object class: ${leafObjectClassName}`);
    return [];
  }

  const reqWithLeafObjectClass: TraceObjQueryReq = {
    ...req,
    filter: {...req.filter, leaf_object_classes: [leafObjectClassName]},
  };

  const objectPromise = client.objsQuery(reqWithLeafObjectClass);

  const objects = await objectPromise;

  // We would expect that this filtering does not filter anything
  // out because the backend enforces the leaf object class, but this
  // is here as a sanity check.
  const filteredObjects = objects.objs
    .map(obj => ({obj, parsed: knownObjectClass.safeParse(obj.val)}))
    .map(({obj, parsed}) => {
      if (!parsed.success) {
        console.warn(
          `Failed to parse object: ${JSON.stringify(parsed.error.errors)}`
        );
      }
      return {obj, parsed};
    })
    .filter(({parsed}) => parsed.success)
    .filter(({obj}) => obj.leaf_object_class === leafObjectClassName)
    .map(
      ({obj, parsed}) =>
        ({...obj, val: parsed.data} as TraceObjSchema<
          BaseObjectClassType<C>,
          C
        >)
    );
  return filteredObjects;
};

export const useCreateBuiltinObjectInstance = <
  C extends BuiltinObjectClassRegistryKeys,
  T = BaseObjectClassType<C>
>(
  objectClassName: C
): ((req: TraceObjCreateReq<T>) => Promise<TraceObjCreateRes>) => {
  const getTsClient = useGetTraceServerClientContext();
  const client = getTsClient();
  return (req: TraceObjCreateReq<T>) =>
    createBuiltinObjectInstance(client, objectClassName, req);
};

export const createBuiltinObjectInstance = async <
  C extends BuiltinObjectClassRegistryKeys,
  T = BaseObjectClassType<C>
>(
  client: TraceServerClient,
  builtinObjectClassName: C,
  req: TraceObjCreateReq<T>
): Promise<TraceObjCreateRes> => {
  if (
    req.obj.builtin_object_class != null &&
    req.obj.builtin_object_class !== builtinObjectClassName
  ) {
    throw new Error(
      `object_class must match objectClassName: ${builtinObjectClassName}`
    );
  }

  const knownBuiltinObjectClass =
    builtinObjectClassRegistry[builtinObjectClassName];
  if (!knownBuiltinObjectClass) {
    throw new Error(`Unknown object class: ${builtinObjectClassName}`);
  }

  const verifiedObject = knownBuiltinObjectClass.safeParse(req.obj.val);

  if (!verifiedObject.success) {
    throw new Error(
      `Invalid object: ${JSON.stringify(verifiedObject.error.errors)}`
    );
  }

  const reqWithBaseObjectClass: TraceObjCreateReq = {
    ...req,
    obj: {
      ...req.obj,
      builtin_object_class: builtinObjectClassName,
    },
  };

  return client.objCreate(reqWithBaseObjectClass);
};
