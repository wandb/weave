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

const ARROW = '→';

type CompareGridCellProps = {
  path: ObjectPath;
  displayType: 'both' | 'diff';
  value: any;
  valueType: any;
  compareValue: any;
  compareValueType: any;
  rowChangeType: any;
};

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
    // TODO: Need to figure out how to override font to be 'Source Sans Pro'
    return (
      <div className="m-[-6px] flex items-start text-xs">
        <ReactDiffViewer
          oldValue={compareValue}
          newValue={value}
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
