import * as w from '@wandb/weave/core';
import React, {useEffect, useMemo} from 'react';

import {useNodeValue} from '../../../react';
import {Select} from '../../Form/Select';
import {Icon} from '../../Icon';
import {ChildPanelFullConfig} from '../ChildPanel';
import {
  customEntitySelectComps,
  customReportSelectComps,
} from './customSelectComponents';
import {
  NEW_REPORT_OPTION,
  DEFAULT_REPORT_OPTION,
  EntityOption,
  ReportOption,
  useEntityAndProject,
  GroupedReportOption,
} from './utils';
import {Button} from '../../Button';

type SelectedExistingReportProps = {
  selectedReport: ReportOption;
  setSelectedReport: (report: ReportOption | null) => void;
};

export const SelectedExistingReport = ({
  selectedReport,
  setSelectedReport,
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
          icon="close"
          variant="ghost"
          className="flex shrink-0 text-moon-500"
          onClick={() => setSelectedReport(null)}
        />
      </div>
    </div>
  );
};
