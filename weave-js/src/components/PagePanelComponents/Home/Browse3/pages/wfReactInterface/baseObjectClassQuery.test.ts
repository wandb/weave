import {useCollectionObjects} from './baseObjectClassQuery';
import {TestOnlyExampleSchema} from './generatedBaseObjectClasses.zod';
describe('useCollectionObjects', () => {
  it('hasCorrectTypes', () => {
    type CT = ReturnType<typeof useCollectionObjects<'TestOnlyExample'>>;
    const exampleResult: CT = {
      loading: false,
      data: [
        {
          project_id: '',
          object_id: '',
          created_at: '',
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
    // This should fail, looking for the correct way to validate types
    expect(exampleResult).toBeNull();
  });
});
