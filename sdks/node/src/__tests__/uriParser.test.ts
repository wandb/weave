import {parseWeaveUri} from '../uriParser';
import {ObjectRef} from '../weaveObject';

describe('parseWeaveUri', () => {
  describe('registry:/// URIs', () => {
    it('should parse registry:/// object refs', () => {
      const result = parseWeaveUri(
        'registry:///my-org/my-project/object/my-prompt:v0'
      );
      expect(result).toEqual({
        type: 'object',
        entity: 'my-org',
        project: 'my-project',
        name: 'my-prompt',
        digest: 'v0',
      });
    });

    it('should parse registry:/// op refs', () => {
      const result = parseWeaveUri(
        'registry:///my-org/my-project/op/my-op:abc123'
      );
      expect(result).toEqual({
        type: 'op',
        entity: 'my-org',
        project: 'my-project',
        name: 'my-op',
        digest: 'abc123',
      });
    });

    it('should default to latest digest for registry:/// refs without version', () => {
      const result = parseWeaveUri(
        'registry:///my-org/my-project/object/my-prompt'
      );
      expect(result).toEqual({
        type: 'object',
        entity: 'my-org',
        project: 'my-project',
        name: 'my-prompt',
        digest: 'latest',
      });
    });

    it('should handle special characters in entity and project', () => {
      const result = parseWeaveUri(
        "registry:///wandb32/wandb-registry-Matt's Prompts/object/weave prompts:latest"
      );
      expect(result).toEqual({
        type: 'object',
        entity: 'wandb32',
        project: "wandb-registry-Matt's Prompts",
        name: 'weave prompts',
        digest: 'latest',
      });
    });
  });

  describe('weave:/// URIs (regression)', () => {
    it('should still parse weave:/// object refs', () => {
      const result = parseWeaveUri(
        'weave:///my-entity/my-project/object/my-dataset:def456'
      );
      expect(result).toEqual({
        type: 'object',
        entity: 'my-entity',
        project: 'my-project',
        name: 'my-dataset',
        digest: 'def456',
      });
    });

    it('should still parse weave:/// table refs', () => {
      const result = parseWeaveUri(
        'weave:///my-entity/my-project/table/abc123'
      );
      expect(result).toEqual({
        type: 'table',
        entity: 'my-entity',
        project: 'my-project',
        digest: 'abc123',
      });
    });

    it('should still parse weave:/// call refs', () => {
      const result = parseWeaveUri(
        'weave:///my-entity/my-project/call/call-uuid'
      );
      expect(result).toEqual({
        type: 'call',
        entity: 'my-entity',
        project: 'my-project',
        id: 'call-uuid',
      });
    });
  });

  describe('invalid URIs', () => {
    it('should return null for other schemes', () => {
      expect(parseWeaveUri('http://example.com')).toBeNull();
      expect(parseWeaveUri('ftp:///entity/project/object/name:v0')).toBeNull();
    });

    it('should return null for malformed URIs', () => {
      expect(parseWeaveUri('')).toBeNull();
      expect(parseWeaveUri('weave://missing-slash')).toBeNull();
      expect(parseWeaveUri('registry://only-two-slashes')).toBeNull();
      expect(parseWeaveUri('weave:///too/few')).toBeNull();
    });

    it('should return null for unknown ref types', () => {
      expect(
        parseWeaveUri('weave:///entity/project/unknown/something')
      ).toBeNull();
      expect(
        parseWeaveUri('registry:///entity/project/unknown/something')
      ).toBeNull();
    });
  });
});

describe('ObjectRef.fromUri', () => {
  describe('registry:/// URIs', () => {
    it('should create ObjectRef from registry:/// object URI', () => {
      const ref = ObjectRef.fromUri(
        'registry:///my-org/my-project/object/my-prompt:v0'
      );
      expect(ref.projectId).toBe('my-org/my-project');
      expect(ref.objectId).toBe('my-prompt');
      expect(ref.digest).toBe('v0');
    });

    it('should create ObjectRef from registry:/// with latest digest', () => {
      const ref = ObjectRef.fromUri(
        'registry:///my-org/my-project/object/my-prompt'
      );
      expect(ref.projectId).toBe('my-org/my-project');
      expect(ref.objectId).toBe('my-prompt');
      expect(ref.digest).toBe('latest');
    });
  });

  describe('error cases', () => {
    it('should throw for non-object registry:/// URIs', () => {
      expect(() =>
        ObjectRef.fromUri('registry:///entity/project/table/digest')
      ).toThrow('Invalid object ref URI');
    });

    it('should throw for invalid URIs', () => {
      expect(() => ObjectRef.fromUri('not-a-uri')).toThrow(
        'Invalid object ref URI'
      );
    });
  });
});
