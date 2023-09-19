import React, {useState} from 'react';
import _ from 'lodash';

import {Alert} from '../../Alert.styles';
import {Button} from '../../Button';
import {Tailwind} from '../../Tailwind';
import {useCloseDrawer, useSelectedPath} from '../PanelInteractContext';
import {ReportSelection} from './ReportSelection';
import {ChildPanelFullConfig} from '../ChildPanel';
import {EntityOption, ProjectOption, ReportOption} from './utils';

type ChildPanelExportReportProps = {
  rootConfig: ChildPanelFullConfig;
};

export const ChildPanelExportReport = ({
  rootConfig,
}: ChildPanelExportReportProps) => {
  const selectedPath = useSelectedPath();
  const closeDrawer = useCloseDrawer();

  const [selectedEntity, setSelectedEntity] = useState<EntityOption | null>(
    null
  );
  const [selectedReport, setSelectedReport] = useState<ReportOption | null>(
    null
  );
  const [selectedProject, setSelectedProject] = useState<ProjectOption | null>(
    null
  );

  const onAddPanel = () => {
    // TODO - this will be replaced with correct add panel implementation later on
    alert(
      `Report id: ${selectedReport?.id} \nReport name: ${selectedReport?.name} \nEntity name: ${selectedEntity?.name} \nProject name: ${selectedProject?.name}`
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
            rootConfig={rootConfig}
            selectedEntity={selectedEntity}
            selectedReport={selectedReport}
            selectedProject={selectedProject}
            setSelectedEntity={setSelectedEntity}
            setSelectedReport={setSelectedReport}
            setSelectedProject={setSelectedProject}
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
            disabled={selectedReport == null || selectedProject == null}
            onClick={onAddPanel}>
            Add panel
          </Button>
        </div>
      </div>
    </Tailwind>
  );
};
