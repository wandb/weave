import React from 'react';

import {LoadingDots} from '../../../../../LoadingDots';
import {Timestamp} from '../../../../../Timestamp';
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
  const {useFileContent} = useWFHooks();
  const datetimeKey = 'obj.json';
  const isCustomType = data != null && typeof data === 'object';
  const fileDigest =
    isCustomType && datetimeKey in data.files ? data.files[datetimeKey] : '';
  const datetimeBinary = useFileContent(
    entity || '',
    project || '',
    fileDigest,
    {skip: !isCustomType || !(datetimeKey in data.files)}
  );

  // Handle null/undefined cases early
  if (data == null) {
    return <NotApplicable />;
  }

  // Handle direct ISO string input
  if (typeof data === 'string') {
    const stringTimestamp = new Date(data).getTime() / 1000;
    return <Timestamp value={stringTimestamp} format="relative" />;
  }

  // Handle CustomWeaveTypePayload
  if (!(datetimeKey in data.files)) {
    return <NotApplicable />;
  }

  if (datetimeBinary.loading) {
    return <LoadingDots />;
  }

  if (datetimeBinary.result == null) {
    return <NotApplicable />;
  }

  const content = JSON.parse(new TextDecoder().decode(datetimeBinary.result));
  if (!content.isoformat) {
    return <NotApplicable />;
  }

  const customTypeTimestamp = new Date(content.isoformat).getTime() / 1000;
  return <Timestamp value={customTypeTimestamp} format="relative" />;
};
