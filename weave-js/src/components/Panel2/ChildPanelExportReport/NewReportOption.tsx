import React from 'react';
import {
  DEFAULT_REPORT_OPTION,
  EntityOption,
  GroupedReportOption,
  NEW_REPORT_OPTION,
  ReportOption,
  formatUpdatedAt,
} from './utils';
import {Icon} from '../../Icon';
import TimeAgo from 'react-timeago';
import {size} from 'lodash';
import {MOON_250} from '../../../common/css/color.styles';
import {Group} from '../../../common/util/data';
import {twMerge} from 'tailwind-merge';

type NewReportOptionProps = {
  optionData: ReportOption;
  children: React.ReactNode;
};
export const NewReportOption = ({
  optionData,
  children,
}: NewReportOptionProps) => {
  return (
    <div
      className={twMerge(
        'flex grow',
        optionData.name === NEW_REPORT_OPTION && 'items-center'
      )}>
      {optionData.name === NEW_REPORT_OPTION ? (
        <Icon name="add-new" width={18} height={18} />
      ) : (
        <Icon name="report" className="shrink-0 grow-0 pt-4" />
      )}
      <p className="mx-8 flex grow flex-col gap-4 p-0 text-base leading-6">
        <span>{children}</span>
        <span className="text-sm text-moon-500">{optionData.projectName}</span>
      </p>
    </div>
  );
};
