import {useWindowSize} from '@wandb/weave/common/hooks/useWindowSize';
import {useMemo} from 'react';

export const useFlexDirection = () => {
  const windowSize = useWindowSize();

  const flexDirection = useMemo(() => {
    if (windowSize.height > windowSize.width * 0.66) {
      return 'column';
    }
    return 'row';
  }, [windowSize.height, windowSize.width]);
  return flexDirection;
};
