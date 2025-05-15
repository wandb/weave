import React from 'react';

type SavedViewSuffixTimestampProps = {
  createdAt: string;
};

export const SavedViewSuffixTimestamp = ({
  createdAt,
}: SavedViewSuffixTimestampProps) => {
  // Jul 25 at 5:22pm
  const saveTime = new Date(createdAt)
    .toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    })
    .replace(', ', ' at ')
    .replace(/AM|PM/, match => match.toLowerCase());

  return <>{saveTime}</>;
};
