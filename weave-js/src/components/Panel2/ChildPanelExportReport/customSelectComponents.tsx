import React from 'react';
import {
  components as selectComponents,
  GroupHeadingProps,
  GroupProps,
  MenuListProps,
  OptionProps,
  SingleValueProps,
} from 'react-select';
import TimeAgo from 'react-timeago';

import {Icon} from '../../Icon';
import {ReportOptionComp} from './ReportOption';
import {
  EntityOption,
  formatUpdatedAt,
  GroupedReportOption,
  ReportOption,
} from './utils';

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
  SingleValue: ({
    children,
    ...props
  }: SingleValueProps<ReportOption, false, GroupedReportOption>) => (
    <selectComponents.SingleValue
      {...props}
      className="flex items-center gap-8">
      <Icon name="add-new" width={18} height={18} />
      {children}
    </selectComponents.SingleValue>
  ),
  MenuList: (
    props: MenuListProps<ReportOption, false, GroupedReportOption>
  ) => (
    <selectComponents.MenuList
      {...props}
      className="max-h-[calc(100vh-34rem)]"
    />
  ),
  GroupHeading: (
    groupHeadingProps: GroupHeadingProps<
      ReportOption,
      false,
      GroupedReportOption
    >
  ) => {
    const isFirstGroup =
      groupHeadingProps.selectProps.options.findIndex(
        option => option === groupHeadingProps.data
      ) === 0;
    return (
      <selectComponents.GroupHeading {...groupHeadingProps} className="">
        {!isFirstGroup && <hr className="my-8 h-1 border-moon-250" />}
      </selectComponents.GroupHeading>
    );
  },
  Group: (groupProps: GroupProps<ReportOption, false, GroupedReportOption>) => (
    <selectComponents.Group {...groupProps} className="p-0" />
  ),
  Option: ({
    children,
    ...props
  }: OptionProps<ReportOption, false, GroupedReportOption>) => {
    const optionData: ReportOption = props.data;
    return (
      <selectComponents.Option {...props} className="flex items-center">
        <ReportOptionComp optionData={optionData} children={children} />
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
