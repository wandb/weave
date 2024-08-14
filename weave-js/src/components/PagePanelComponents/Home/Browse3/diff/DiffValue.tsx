import {DiffEditor} from '@monaco-editor/react';
import _ from 'lodash';
import React from 'react';

import {CellValue} from '../../Browse2/CellValue';
import {ADDED, CHANGED, UNCHANGED} from './diff';
import {DiffValueChanged} from './DiffValueChanged';

type DiffValueProps = {
  type: number;
  left: any;
  right: any;
  panels: string[];
};

export const DiffValue = ({type, left, right, panels}: DiffValueProps) => {
  if (type === ADDED) {
    return <CellValue value={right} />;
  }
  if (type === CHANGED) {
    return <DiffValueChanged left={left} right={right} panels={panels} />;
  }
  return <CellValue value={left} align="left" />;
};
