import {makeSettings} from '../settings';

describe('makeSettings', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = {...originalEnv};
    delete process.env.WEAVE_PRINT_CALL_LINK;
    delete process.env.WEAVE_USE_OTEL_V2;
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  describe('defaults', () => {
    it('returns defaults with no args', () => {
      const settings = makeSettings();
      expect(settings).toEqual({
        attributes: {},
        genai: {},
        printCallLink: true,
      });
    });

    it('returns defaults with empty object', () => {
      const settings = makeSettings({});
      expect(settings).toEqual({
        attributes: {},
        genai: {},
        printCallLink: true,
      });
    });
  });

  describe('explicit settings', () => {
    it('honors printCallLink', () => {
      expect(makeSettings({printCallLink: false}).printCallLink).toBe(false);
    });

    it('honors attributes', () => {
      const attrs = {tenant: 'acme', region: 'us-west'};
      expect(makeSettings({attributes: attrs}).attributes).toEqual(attrs);
    });

    it('honors genai settings', () => {
      const genai = {spanProcessor: 'simple' as const};
      expect(makeSettings({genai}).genai).toEqual(genai);
    });
  });

  describe('env var precedence', () => {
    it('WEAVE_PRINT_CALL_LINK=true overrides explicit false', () => {
      process.env.WEAVE_PRINT_CALL_LINK = 'true';
      expect(makeSettings({printCallLink: false}).printCallLink).toBe(true);
    });

    it('WEAVE_PRINT_CALL_LINK=false overrides explicit true', () => {
      process.env.WEAVE_PRINT_CALL_LINK = 'false';
      expect(makeSettings({printCallLink: true}).printCallLink).toBe(false);
    });

    it('WEAVE_PRINT_CALL_LINK parses case-insensitively', () => {
      process.env.WEAVE_PRINT_CALL_LINK = 'FALSE';
      expect(makeSettings().printCallLink).toBe(false);
      process.env.WEAVE_PRINT_CALL_LINK = 'True';
      expect(makeSettings().printCallLink).toBe(true);
    });

    it('WEAVE_PRINT_CALL_LINK with invalid value falls back to explicit setting', () => {
      process.env.WEAVE_PRINT_CALL_LINK = 'maybe';
      expect(makeSettings({printCallLink: false}).printCallLink).toBe(false);
    });

    it('WEAVE_PRINT_CALL_LINK with invalid value falls back to default when no explicit setting', () => {
      process.env.WEAVE_PRINT_CALL_LINK = 'maybe';
      expect(makeSettings().printCallLink).toBe(true);
    });
  });
});
