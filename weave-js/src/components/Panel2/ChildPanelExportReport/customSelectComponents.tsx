import {
  components as selectComponents,
  MenuProps,
  SingleValueProps,
  OptionProps,
} from 'react-select';
import {Icon} from '../../Icon';
import React from 'react';
import {ReportOption} from './utils';
import TimeAgo from 'react-timeago';

export function customSelectComponents<T>() {
  return {
    SingleValue: ({
      children,
      ...props
    }: SingleValueProps<ReportOption, false>) => (
      <selectComponents.SingleValue
        {...props}
        className="flex items-center gap-8">
        {children}
      </selectComponents.SingleValue>
    ),
    Menu: (props: MenuProps<ReportOption, false>) => (
      <selectComponents.Menu {...props} className="" />
    ),
    Option: ({children, ...props}: OptionProps<T, false>) => {
      return (
        <selectComponents.Option {...props} className="flex">
          <Icon name="report" className="pt-4" />
          <p className="ml-8 flex max-w-[90%] flex-col gap-4">
            <span>{children}</span>
            {props.data?.updatedAt ? (
              <span className="text-sm text-moon-500">
                {props.data.updatedByUsername ?? props.data?.updatedByUserName}{' '}
                updated in {props.data?.projectName}{' '}
                <TimeAgo date={props.data?.updatedAt} />
              </span>
            ) : (
              <span className="text-sm text-moon-500">
                {props.data.creatorUsername} created in{' '}
                {props.data?.projectName}{' '}
                <TimeAgo date={props.data?.createdAt} />
              </span>
            )}
          </p>
        </selectComponents.Option>
      );
    },
  };
}
