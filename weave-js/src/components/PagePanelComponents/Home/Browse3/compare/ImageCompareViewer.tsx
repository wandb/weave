import {IconForwardNext} from '@wandb/weave/components/Icon';
import React, {useMemo} from 'react';

import {ValueViewImage} from '../pages/CallPage/ValueViewImage';

type ImageCompareViewerProps = {
  value: string;
  compareValue: string;
};

/**
 * Helper function to process base64 strings.
 *
 * @param imageValue - The image string to process
 * @returns Properly formatted image URL
 */
function processImageValue(imageValue: string): string {
  // If it starts with 'base64:', strip that prefix
  if (imageValue.startsWith('base64:')) {
    const base64Data = imageValue.slice(7); // Remove 'base64:' prefix
    // If it doesn't have data URL format, add it
    if (!base64Data.startsWith('data:')) {
      return `data:image/png;base64,${base64Data}`;
    }
    return base64Data;
  }
  // If it's already a data URL or regular URL, return as is
  return imageValue;
}

/**
 * Component for comparing two base64 images side by side.
 *
 * @param value - The new/current base64 image string
 * @param compareValue - The old/comparison base64 image string
 * @returns JSX element displaying both images side by side
 */
export const ImageCompareViewer = ({
  value,
  compareValue,
}: ImageCompareViewerProps) => {
  const processedValue = useMemo(() => processImageValue(value), [value]);
  const processedCompareValue = useMemo(
    () => processImageValue(compareValue),
    [compareValue]
  );

  // Check if the processed image data is identical
  const areImagesIdentical = useMemo(
    () => processedValue === processedCompareValue,
    [processedValue, processedCompareValue]
  );

  // If images are identical, show single image with "unchanged" message
  if (areImagesIdentical) {
    return (
      <div className="flex flex-col items-center">
        <div className="text-gray-600 mb-2 text-sm font-medium">
          (Image Data Unchanged)
        </div>
        <ValueViewImage value={processedValue} />
      </div>
    );
  }

  // Show side-by-side comparison for different images
  return (
    <div className="flex items-start items-center gap-4">
      <div className="flex flex-col items-center">
        <div className="text-gray-500 mb-2 text-xs">Before</div>
        <ValueViewImage value={processedCompareValue} />
      </div>
      <IconForwardNext />
      <div className="flex flex-col items-center">
        <div className="text-gray-500 mb-2 text-xs">After</div>
        <ValueViewImage value={processedValue} />
      </div>
    </div>
  );
};
