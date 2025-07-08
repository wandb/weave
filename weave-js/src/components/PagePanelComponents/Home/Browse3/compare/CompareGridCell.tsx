/**
 * This handles the logic around the unified diff mode and
 * showing either A -> B (delta) or some specific diff tool.
 */

import _ from 'lodash';
import React from 'react';
import ReactDiffViewer, {DiffMethod} from 'react-diff-viewer';

import {ObjectPath} from '../pages/CallPage/traverse';
import {CodeDiff} from './CodeDiff';
import {CompareGridCellValue} from './CompareGridCellValue';
import {CompareGridPill} from './CompareGridPill';
import {ImageCompareViewer} from './ImageCompareViewer';

const ARROW = '→';
const MAX_STRING_LENGTH_IN_DIFF_VIEW = 10000;

type CompareGridCellProps = {
  path: ObjectPath;
  displayType: 'both' | 'diff';
  value: any;
  valueType: any;
  compareValue: any;
  compareValueType: any;
  rowChangeType: any;
};

function limitStringLength(str: string, maxLength: number) {
  if (str.length > maxLength) {
    return str.slice(0, maxLength) + '...';
  }
  return str;
}

/**
 * Detects if a string is likely a base64 encoded image.
 *
 * @param str - The string to check
 * @returns true if the string appears to be a base64 image
 */
function isBase64Image(str: string): boolean {
  if (!str || typeof str !== 'string') {
    return false;
  }

  // Check for data URL format: data:image/[type];base64,[data]
  if (str.startsWith('data:image/') && str.includes(';base64,')) {
    return true;
  }

  // Check for 'base64:' prefix format
  if (str.startsWith('base64:')) {
    return true;
  }

  return false;
}

export const CompareGridCell = ({
  path,
  displayType,
  value,
  valueType,
  compareValue,
  compareValueType,
  rowChangeType,
}: CompareGridCellProps) => {
  // If all of the row values are the same we can just display the value
  if (rowChangeType === 'UNCHANGED' && _.isEqual(value, compareValue)) {
    return (
      <CompareGridCellValue path={path} value={value} valueType={valueType} />
    );
  }

  if (valueType === 'code' && compareValueType === 'code') {
    return <CodeDiff oldValueRef={compareValue} newValueRef={value} />;
  }

  if (valueType === 'string' && compareValueType === 'string') {
    if (isBase64Image(compareValue) || isBase64Image(value)) {
      return <ImageCompareViewer value={value} compareValue={compareValue} />;
    }
    // TODO: Need to figure out how to override font to be 'Source Sans Pro'
    return (
      <div className="m-[-6px] flex items-start text-xs">
        <ReactDiffViewer
          oldValue={limitStringLength(
            compareValue,
            MAX_STRING_LENGTH_IN_DIFF_VIEW
          )}
          newValue={limitStringLength(value, MAX_STRING_LENGTH_IN_DIFF_VIEW)}
          splitView={false}
          compareMethod={DiffMethod.WORDS}
          hideLineNumbers={true}
          showDiffOnly={false}
        />
      </div>
    );
  }

  return (
    <div className="flex gap-8">
      {displayType === 'both' && (
        <>
          <CompareGridCellValue
            path={path}
            value={compareValue}
            valueType={compareValueType}
          />
          {ARROW}
        </>
      )}
      <CompareGridCellValue path={path} value={value} valueType={valueType} />
      <CompareGridPill
        value={value}
        valueType={valueType}
        compareValue={compareValue}
        compareValueType={compareValueType}
      />
    </div>
  );
};
