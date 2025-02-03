import {expectType} from 'tsd';

import {
  TestOnlyExample,
  TestOnlyExampleSchema,
} from './generatedBuiltinObjectClasses.zod';
import {
  useBaseObjectInstances,
  useCreateBuiltinObjectInstance,
} from './objectClassQuery';
import {
  TraceObjCreateReq,
  TraceObjCreateRes,
  TraceObjSchema,
} from './traceServerClientTypes';
import {Loadable} from './wfDataModelHooksInterface';

type TypesAreEqual<T, U> = [T] extends [U]
  ? [U] extends [T]
    ? true
    : false
  : false;

describe('Type Tests', () => {
  it('useCollectionObjects return type matches expected structure', () => {
    type CollectionObjectsReturn = ReturnType<
      typeof useBaseObjectInstances<'TestOnlyExample'>
    >;

    // Define the expected type structure
    type ExpectedType = Loadable<
      Array<TraceObjSchema<TestOnlyExample, 'TestOnlyExample'>>
    >;

    // Type assertion tests
    type AssertTypesAreEqual = TypesAreEqual<
      CollectionObjectsReturn,
      ExpectedType
    >;
    type Assert = AssertTypesAreEqual extends true ? true : never;

    // This will fail compilation if the types don't match exactly
    const _assert: Assert = true;
    expect(_assert).toBe(true);

    // Additional runtime sample for documentation
    const sampleResult: CollectionObjectsReturn = {
      loading: false,
      result: [
        {
          project_id: '',
          object_id: '',
          created_at: '',
          deleted_at: null,
          digest: '',
          version_index: 0,
          is_latest: 0,
          kind: 'object',
          base_object_class: 'TestOnlyExample',
          val: TestOnlyExampleSchema.parse({
            name: '',
            description: '',
            nested_base_model: {
              a: 1,
            },
            nested_base_object: '',
            primitive: 1,
          }),
        },
      ],
    };

    expectType<ExpectedType>(sampleResult);
  });

  it('useCreateCollectionObject return type matches expected structure', () => {
    type CreateCollectionObjectReturn = ReturnType<
      typeof useCreateBuiltinObjectInstance<'TestOnlyExample'>
    >;

    // Define the expected type structure
    type ExpectedType = (
      req: TraceObjCreateReq<TestOnlyExample>
    ) => Promise<TraceObjCreateRes>;

    // Type assertion tests
    type AssertTypesAreEqual = TypesAreEqual<
      CreateCollectionObjectReturn,
      ExpectedType
    >;
    type Assert = AssertTypesAreEqual extends true ? true : never;

    // This will fail compilation if the types don't match exactly
    const _assert: Assert = true;
    expect(_assert).toBe(true);

    // Additional runtime sample for documentation
    const sampleResult: CreateCollectionObjectReturn = async req => {
      return {
        digest: '',
      };
    };

    expectType<ExpectedType>(sampleResult);
  });
});
