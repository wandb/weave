import {
  components as selectComponents,
  OptionProps,
  SingleValueProps,
  MenuListProps,
} from 'react-select';
import {Icon} from '../../Icon';
import React from 'react';
import {EntityOption, ReportOption, formatUpdatedAt} from './utils';
import TimeAgo from 'react-timeago';

export const customEntitySelectComps = {
  SingleValue: ({
    children,
    ...props
  }: SingleValueProps<EntityOption, false>) => (
    <selectComponents.SingleValue
      {...props}
      className="flex items-center gap-8">
      <Icon
        className="shrink-0 grow-0 "
        name={props.data?.isTeam ? 'users-team' : 'user-profile-personal'}
      />
      <p className="overflow-hidden text-ellipsis">{children}</p>
    </selectComponents.SingleValue>
  ),
  MenuList: (props: MenuListProps<EntityOption, false>) => (
    <selectComponents.MenuList
      {...props}
      className="max-h-[calc(100vh-34rem)]"
    />
  ),
  Option: ({children, ...props}: OptionProps<EntityOption, false>) => {
    return (
      <selectComponents.Option {...props} className="flex items-center  gap-8">
        <Icon
          name={props.data?.isTeam ? 'users-team' : 'user-profile-personal'}
        />
        <span>{children}</span>
      </selectComponents.Option>
    );
  },
};

export const customReportSelectComps = {
  MenuList: (props: MenuListProps<ReportOption, false>) => (
    <selectComponents.MenuList
      {...props}
      className="max-h-[calc(100vh-34rem)]"
    />
  ),
  Option: ({children, ...props}: OptionProps<ReportOption, false>) => {
    const optionData: ReportOption = props.data;
    return (
      <selectComponents.Option {...props} className="flex items-center">
        <div className="flex grow">
          <Icon name="report" className="shrink-0 grow-0 pt-4" />
          <p className="mx-8 flex grow flex-col gap-4">
            <span>{children}</span>
            <span className="text-sm text-moon-500">
              {optionData.projectName}
            </span>
          </p>
        </div>
        {optionData?.updatedAt != null && (
          <p className="shrink-0 text-sm text-moon-500">
            <TimeAgo
              date={optionData.updatedAt}
              live={false}
              formatter={(value, unit, suffix) =>
                formatUpdatedAt({
                  date: optionData.updatedAt ?? 0,
                  value,
                  unit,
                  suffix,
                })
              }
            />
          </p>
        )}
      </selectComponents.Option>
    );
  },
};
