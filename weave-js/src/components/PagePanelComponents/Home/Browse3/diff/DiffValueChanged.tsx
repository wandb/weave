import {DiffEditor} from '@monaco-editor/react';
import _ from 'lodash';
import React, {useState} from 'react';
import {DiffMethod} from 'react-diff-viewer';

import {Button} from '../../../../Button';
import {CellValue} from '../../Browse2/CellValue';
import {isProbablyTimestamp} from '../pages/CallPage/ValueViewNumberTimestamp';
import {ADDED, CHANGED, UNCHANGED} from './diff';
import {ARROW} from './DiffValueCommon';
import {DiffValueLongString} from './DiffValueLongString';
import {DiffValueNumber} from './DiffValueNumber';
import {DiffValueString} from './DiffValueString';
import {DiffValueTimestamp} from './DiffValueTimestamp';

type DiffValueChangedProps = {
  left: any;
  right: any;
  panels: string[];
};

export const DiffValueChanged = ({
  left,
  right,
  panels,
}: DiffValueChangedProps) => {
  const [panelIdx, setPanelIdx] = useState(0);
  if (panels.length === 0) {
    return null;
  }

  const onClick = () => {
    setPanelIdx((panelIdx + 1) % panels.length);
  };

  const panel = panels[panelIdx];

  return (
    <div className="flex w-full gap-4">
      <Button
        size="small"
        variant="quiet"
        icon="show-visible"
        onClick={onClick}
        disabled={panels.length <= 1}
        tooltip="Click to cycle through diff techniques"
      />
      {panel === 'Timestamp' && (
        <DiffValueTimestamp left={left} right={right} />
      )}
      {panel === 'Number' && <DiffValueNumber left={left} right={right} />}
      {panel === 'LongStringUnified' && (
        <DiffValueLongString
          left={left}
          right={right}
          renderSideBySide={false}
        />
      )}
      {panel === 'LongStringSideBySide' && (
        <DiffValueLongString
          left={left}
          right={right}
          renderSideBySide={true}
        />
      )}
      {/* CHARS = "diffChars", WORDS = "diffWords", WORDS_WITH_SPACE =
      "diffWordsWithSpace", LINES = "diffLines", TRIMMED_LINES =
      "diffTrimmedLines", SENTENCES = "diffSentences", CSS = "diffCss" */}
      {panel === 'StringChars' && (
        <DiffValueString
          left={left}
          right={right}
          compareMethod={DiffMethod.CHARS}
        />
      )}
      {panel === 'StringWords' && (
        <DiffValueString
          left={left}
          right={right}
          compareMethod={DiffMethod.WORDS}
        />
      )}
      {panel === 'StringLines' && (
        <DiffValueString
          left={left}
          right={right}
          compareMethod={DiffMethod.LINES}
        />
      )}
      {panel === 'SideBySide' && (
        <div className="flex gap-16">
          <CellValue value={left} />
          {ARROW}
          <CellValue value={right} />
        </div>
      )}
    </div>
  );
};
