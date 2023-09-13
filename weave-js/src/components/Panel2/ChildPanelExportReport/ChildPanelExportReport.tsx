import React, {useEffect, useState} from 'react';
import _ from 'lodash';

import {Alert} from '../../Alert.styles';
import {Button} from '../../Button';
import {Tailwind} from '../../Tailwind';
import {useCloseDrawer, useSelectedPath} from '../PanelInteractContext';
import {ReportSelection} from './ReportSelection';
import {ChildPanelFullConfig} from '../ChildPanel';
import {ReportOption, useEntityAndProject} from './utils';

type ChildPanelExportReportProps = {
  config: ChildPanelFullConfig;
};

export const ChildPanelExportReport = ({
  config,
}: ChildPanelExportReportProps) => {
  const selectedPath = useSelectedPath();
  const closeDrawer = useCloseDrawer();

  const {entityName} = useEntityAndProject(config);
  useEffect(() => {
    setSelectedEntityName(entityName);
  }, [entityName]);

  const [selectedEntityName, setSelectedEntityName] =
    useState<string>(entityName);
  const [selectedReport, setSelectedReport] = useState<ReportOption | null>(
    null
  );

  const onAddPanel = () => {
    alert(
      `Report id: ${selectedReport?.id} \nReport name: ${selectedReport?.name} \nEntity name: ${selectedEntityName}`
    );
  };

  return (
    <Tailwind style={{height: '100%'}}>
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-moon-250 px-16 py-12">
          <h2 className="text-lg font-semibold">
            Add {_.last(selectedPath)} to report
          </h2>
          <Button icon="close" variant="ghost" onClick={closeDrawer} />
        </div>
        <div className="flex-1 gap-8 p-16">
          <Alert severity="warning">
            <p>
              <b>🚧 Work in progress!</b> This feature is under development
              behind an internal-only feature flag.
            </p>
          </Alert>
          <ReportSelection
            config={config}
            selectedEntityName={selectedEntityName}
            selectedReport={selectedReport}
            setSelectedEntityName={setSelectedEntityName}
            setSelectedReport={setSelectedReport}
          />
          <p className="mt-16 text-moon-500">
            Future changes to the board will not affect exported panels inside
            reports.
          </p>
        </div>
        <div className="border-t border-moon-250 px-16 py-20">
          <Button
            icon="add-new"
            className="w-full"
            disabled={!selectedEntityName && !selectedReport}
            onClick={onAddPanel}>
            Add panel
          </Button>
        </div>
      </div>
    </Tailwind>
  );
};
