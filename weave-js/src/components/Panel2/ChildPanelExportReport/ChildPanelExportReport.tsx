import React from 'react';
import _ from 'lodash';

import {Alert} from '../../Alert.styles';
import {Button} from '../../Button';
import {Tailwind} from '../../Tailwind';
import {useCloseDrawer, useSelectedPath} from '../PanelInteractContext';

export const ChildPanelExportReport = () => {
  const selectedPath = useSelectedPath();
  const closeDrawer = useCloseDrawer();

  return (
    <Tailwind style={{height: '100%'}}>
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-moon-250 px-16 py-12">
          <h2 className="text-lg font-semibold">
            Add {_.last(selectedPath)} to report
          </h2>
          <Button icon="close" variant="ghost" onClick={closeDrawer} />
        </div>
        <div className="flex-1 p-16">
          <Alert severity="warning">
            <p>
              <b>🚧 Work in progress!</b> This feature is under development
              behind an internal-only feature flag.
            </p>
          </Alert>
          <p className="mt-16 text-moon-500">
            Future changes to the board will not affect exported panels inside
            reports.
          </p>
        </div>
        <div className="border-t border-moon-250 px-16 py-20">
          <Button icon="add-new" className="w-full" disabled>
            Add panel
          </Button>
        </div>
      </div>
    </Tailwind>
  );
};
