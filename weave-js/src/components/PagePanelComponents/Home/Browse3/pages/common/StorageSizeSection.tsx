import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {convertBytes} from '@wandb/weave/util';
import React, {useMemo} from 'react';

interface StorageSizeSectionProps {
  isLoading?: boolean;
  currentVersionBytes?: number;
  allVersionsSizeBytes?: number;
  shouldShowAllVersions: boolean;
}
export const StorageSizeSection: React.FC<StorageSizeSectionProps> = ({
  currentVersionBytes,
  isLoading,
  allVersionsSizeBytes,
  shouldShowAllVersions,
}) => {
  const presentation = useMemo(() => {
    if (isLoading) {
      return <LoadingDots />;
    }

    if (currentVersionBytes === undefined) {
      return 'Not available';
    }

    let allVersionsSize = '';
    if (shouldShowAllVersions) {
      allVersionsSize = ` (${convertBytes(
        allVersionsSizeBytes
      )} from all versions)`;
    }

    return `${convertBytes(currentVersionBytes)}${allVersionsSize}`;
  }, [
    currentVersionBytes,
    isLoading,
    allVersionsSizeBytes,
    shouldShowAllVersions,
  ]);

  return (
    <div className="block">
      <p className="text-moon-500">Storage size</p>
      {presentation}
    </div>
  );
};
