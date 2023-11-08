import React from 'react';
import {twMerge} from 'tailwind-merge';

import {Icon} from '../../Icon';
import {isNewReportOption, ReportOption} from './utils';

type ReportOptionProps = {
  optionData: ReportOption;
  children: React.ReactNode;
};
export const ReportOptionComp = ({optionData, children}: ReportOptionProps) => {
  return (
    <div
      className={twMerge(
        'flex grow',
        isNewReportOption(optionData) && 'items-center'
      )}>
      {isNewReportOption(optionData) ? (
        <Icon name="add-new" width={18} height={18} />
      ) : (
        <Icon name="report" className="shrink-0 grow-0 pt-4" />
      )}
      <div className="mx-8 flex grow flex-col p-0 text-base leading-6">
        <p>{children}</p>
        {!!optionData.projectName && (
          <p className="mt-4 text-sm text-moon-500">{optionData.projectName}</p>
        )}
      </div>
    </div>
  );
};
