import React from 'react';
import {Timestamp} from '../../../../../Timestamp';
import {LoadingDots} from '../../../../../LoadingDots';
import {NotApplicable} from '../../NotApplicable';
import {useWFHooks} from '../../pages/wfReactInterface/context';
import {CustomWeaveTypePayload} from '../customWeaveType.types';

type DateTimeTypePayload = CustomWeaveTypePayload<
  'datetime.datetime',
  {'obj.json': string}
>;

type DateTimeViewProps = {
  entity?: string;
  project?: string;
  data: DateTimeTypePayload | string | null | undefined;
};

export const DateTimeView = ({entity, project, data}: DateTimeViewProps) => {
  // Handle null/undefined cases early
  if (data == null) {
    return <NotApplicable />;
  }

  // Handle direct ISO string input
  if (typeof data === 'string') {
    const timestamp = new Date(data).getTime() / 1000;
    return <Timestamp value={timestamp} format="relative" />;
  }

  // Handle CustomWeaveTypePayload
  const {useFileContent} = useWFHooks();
  const datetimeKey = 'obj.json';
  const datetimeBinary = useFileContent(
    entity || '',
    project || '',
    data.files[datetimeKey] || '',
    {skip: !(datetimeKey in data.files)}
  );

  if (!(datetimeKey in data.files)) {
    return <NotApplicable />;
  }

  if (datetimeBinary.loading) {
    return <LoadingDots />;
  }

  if (datetimeBinary.result == null) {
    return <NotApplicable />;
  }

  try {
    const content = JSON.parse(new TextDecoder().decode(datetimeBinary.result));

    if (!content.isoformat) {
      return <NotApplicable />;
    }

    const timestamp = new Date(content.isoformat).getTime() / 1000;
    return <Timestamp value={timestamp} format="relative" />;
  } catch (error) {
    return <NotApplicable />;
  }
};
