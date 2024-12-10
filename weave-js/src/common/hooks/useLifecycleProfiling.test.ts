import {renderHook} from '@testing-library/react-hooks';
import {vi} from 'vitest';

import {useLifecycleProfiling} from './useLifecycleProfiling';

describe('useLifecycleProfiling', () => {
  it('tracks the lifecycle of a React component from start to finish', () => {
    const onUnmount = vi.fn();
    const onMount = vi.fn()
    const result = renderHook(() => useLifecycleProfiling('my-component', onUnmount, onMount));

    // Hook returns nothing:
    expect(result.current).toBe(undefined);

    // Hook calls the onStart callback immediately
    expect(onMount).toHaveBeenCalledWith('my-component')
    result.unmount();

    expect(onUnmount).toHaveBeenCalledTimes(1);
    const [{ start, stop, duration, id }] = onUnmount.mock.lastCall

    expect(typeof start).toBe('number')
    expect(typeof stop).toBe('number')
    expect(typeof duration).toBe('number')
    expect(id).toBe('my-component')
  });
});