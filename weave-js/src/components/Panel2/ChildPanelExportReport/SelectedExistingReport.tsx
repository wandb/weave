import React from 'react';

import {Button} from '../../Button';
import {Icon} from '../../Icon';
import {ReportOption} from './utils';

type SelectedExistingReportProps = {
  selectedReport: ReportOption;
  clearSelectedReport: () => void;
};

export const SelectedExistingReport = ({
  selectedReport,
  clearSelectedReport,
}: SelectedExistingReportProps) => {
  return (
    <div className="mb-16 flex rounded bg-moon-50 p-8 text-moon-800">
      <Icon name="report" className="shrink-0 grow-0 pt-4" />
      <div className="flex grow items-center justify-between">
        <p className="mx-8 flex  grow flex-col items-baseline gap-4">
          <span className="text-left">{selectedReport.name}</span>
          <span className="text-sm text-moon-500">
            {selectedReport.projectName}
          </span>
        </p>
        <Button
          aria-label="deselect report option"
          icon="close"
          variant="ghost"
          className="flex shrink-0 text-moon-500"
          onClick={clearSelectedReport}
        />
      </div>
    </div>
  );
};
