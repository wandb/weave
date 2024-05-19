import {parseRef} from './react';

describe('parseRef', () => {
  describe('parsing weave ref', () => {
    it('parses a ref without slashes in name', () => {
      const parsed = parseRef(
        'weave:///entity/project/object/artifact-name:artifactversion'
      );
      expect(parsed).toEqual({
        artifactName: 'artifact-name',
        artifactRefExtra: '',
        artifactVersion: 'artifactversion',
        entityName: 'entity',
        projectName: 'project',
        scheme: 'weave',
        weaveKind: 'object',
      });
    });
    it('parses a ref without slashes in name and with extra', () => {
      const parsed = parseRef(
        'weave:///entity/project/object/artifact-name:artifactversion/attr/rows/id/rowversion'
      );
      expect(parsed).toEqual({
        artifactName: 'artifact-name',
        artifactRefExtra: 'attr/rows/id/rowversion',
        artifactVersion: 'artifactversion',
        entityName: 'entity',
        projectName: 'project',
        scheme: 'weave',
        weaveKind: 'object',
      });
    });
    it('parses a ref with slashes in name', () => {
      const parsed = parseRef(
        'weave:///entity/project/object/a/b/c:artifactversion'
      );
      expect(parsed).toEqual({
        artifactName: 'a/b/c',
        artifactRefExtra: '',
        artifactVersion: 'artifactversion',
        entityName: 'entity',
        projectName: 'project',
        scheme: 'weave',
        weaveKind: 'object',
      });
    });
    it('parses a ref with slashes in name and with extra', () => {
      const parsed = parseRef(
        'weave:///entity/project/object/a/b/c:artifactversion/attr/rows/id/rowversion'
      );
      expect(parsed).toEqual({
        scheme: 'weave',
        artifactName: 'a/b/c',
        artifactRefExtra: 'attr/rows/id/rowversion',
        artifactVersion: 'artifactversion',
        entityName: 'entity',
        projectName: 'project',
        weaveKind: 'object',
      });
    });
  });
  it('parses a weave table ref', () => {
    const parsed = parseRef(
      'weave:///entity/project/table/b8dfcb84974c481fd98fd9878e56be02ebef3e2da44becb59d1863cd643b83fe'
    );
    expect(parsed).toEqual({
      scheme: 'weave',
      artifactName: '',
      artifactRefExtra: '',
      artifactVersion:
        'b8dfcb84974c481fd98fd9878e56be02ebef3e2da44becb59d1863cd643b83fe',
      entityName: 'entity',
      projectName: 'project',
      weaveKind: 'table',
    });
  });
  it('parses an op ref with * as version', () => {
    const parsed = parseRef('weave:///entity/project/op/op-name:*');
    expect(parsed).toEqual({
      artifactName: 'op-name',
      artifactRefExtra: '',
      artifactVersion: '*',
      entityName: 'entity',
      projectName: 'project',
      scheme: 'weave',
      weaveKind: 'op',
    });
  });
});
