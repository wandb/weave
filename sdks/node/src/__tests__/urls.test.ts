import {OpRef} from '../opType';
import {encodeProjectId, setGlobalDomain} from '../urls';
import {ObjectRef} from '../weaveObject';

describe('encodeProjectId', () => {
  it('leaves an ordinary id byte for byte unchanged', () => {
    expect(encodeProjectId('wandb/my-project')).toBe('wandb/my-project');
  });

  it('encodes every segment and keeps the separator', () => {
    // Per segment, not whole-string: `encodeURIPath('my entity/my project')`
    // returns `my%20entity%2Fmy%20project`, collapsing two segments into one.
    // The `#` also rules out a bare `encodeURI`, which would leave it raw.
    expect(encodeProjectId('my entity/my project#1')).toBe(
      'my%20entity/my%20project%231'
    );
  });

  it('encodes non-ASCII characters', () => {
    expect(encodeProjectId('wandb/проект')).toBe(
      'wandb/%D0%BF%D1%80%D0%BE%D0%B5%D0%BA%D1%82'
    );
  });

  it('leaves characters that are legal in a path segment alone', () => {
    expect(encodeProjectId('wandb/a+b&c:d(e)')).toBe('wandb/a+b&c:d(e)');
  });
});

describe('ui_url()', () => {
  beforeEach(() => {
    setGlobalDomain('wandb.ai');
  });

  it('encodes the project and object name in ObjectRef.ui_url()', () => {
    const ref = new ObjectRef('wandb/my project', 'café', 'abc123');
    expect(ref.ui_url()).toBe(
      'https://wandb.ai/wandb/my%20project/weave/objects/caf%C3%A9/versions/abc123'
    );
  });

  it('encodes the project and op name in OpRef.ui_url()', () => {
    const ref = new OpRef('wandb/my project', 'café', 'abc123');
    expect(ref.ui_url()).toBe(
      'https://wandb.ai/wandb/my%20project/weave/ops/caf%C3%A9/versions/abc123'
    );
  });
});
