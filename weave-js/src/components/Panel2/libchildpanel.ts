import {produce} from 'immer';
import {useCallback} from 'react';

export const useChildUpdateConfig2 = (
  panelId: string,
  parentUpdateConfig2?: <P>(change: (oldConfig: P) => Partial<P>) => void
) => {
  return useCallback<any>(
    (change: <T>(oldConfig: T) => Partial<T>) => {
      if (parentUpdateConfig2 == null) {
        return;
      }
      parentUpdateConfig2((currentConfig: any) => {
        const configChanges = change(currentConfig);
        const newConfig = produce(currentConfig, (draft: any) => {
          for (const key of Object.keys(configChanges)) {
            (draft as any)[key] = (configChanges as any)[key];
          }
        });
        return newConfig;
      });
    },
    [parentUpdateConfig2]
  );
};
