import React, {useState} from 'react';

import {Button} from '../../../../Button';
import {ObjectViewerSectionNonEmptyMemoed} from '../pages/CallPage/ObjectViewerSection';
import {ObjectPath} from '../pages/CallPage/traverse';
import {ADDED, CHANGED, DELETED, diff, UNCHANGED} from './diff';
import {DiffGrid} from './DiffGrid';
import {computePanels} from './panels';
import {RowData} from './types';

type ObjectDiffProps = {
  objectType: string;
  left: any;
  right: any;
};

export const ObjectDiff = ({objectType, left, right}: ObjectDiffProps) => {
  const [diffFilter, setDiffFilter] = useState('all');
  const diffResult = diff(left, right).map(d => ({
    type: d.t,
    path: new ObjectPath(d.p),
    left: d.l,
    right: d.r,
  }));
  const diffResultFiltered: RowData[] = diffResult
    .filter(d => {
      if (diffFilter === 'all') {
        return true;
      }
      if (diffFilter === 'different') {
        return d.type !== UNCHANGED;
      }
      if (diffFilter === 'deleted') {
        return d.type === DELETED;
      }
      if (diffFilter === 'added') {
        return d.type === ADDED;
      }
      if (diffFilter === 'changed') {
        return d.type === CHANGED;
      }
      return false;
    })
    .map(d => ({
      ...d,
      panels: computePanels(objectType, d.path, d.left, d.right),
    }));
  return (
    <div>
      <div className="min-h-[40px]">
        <Button
          variant="quiet"
          icon="row-height-small"
          active={diffFilter === 'all'}
          onClick={() => setDiffFilter('all')}
          tooltip="View entire object"
        />
        <Button
          variant="quiet"
          icon="warning"
          active={diffFilter === 'different'}
          onClick={() => setDiffFilter('different')}
          tooltip="View changes"
        />
        <Button
          variant="quiet"
          icon="remove"
          active={diffFilter === 'deleted'}
          onClick={() => setDiffFilter('deleted')}
          tooltip="View deleted"
        />
        <Button
          variant="quiet"
          icon="add-new"
          active={diffFilter === 'added'}
          onClick={() => setDiffFilter('added')}
          tooltip="View added"
        />
        <Button
          variant="quiet"
          icon="pan-tool-1"
          active={diffFilter === 'changed'}
          onClick={() => setDiffFilter('changed')}
          tooltip="View changes"
        />
      </div>
      {diffResultFiltered.length > 0 && <DiffGrid rows={diffResultFiltered} />}
      {diffResultFiltered.length === 0 && (
        <div className="p-8">Nothing {diffFilter}</div>
      )}

      {/* {diffResultFiltered.map((d, i) => {
        const key = d.path.toString();
        return (
          <div key={key}>
            {d.type} {key} {d.left} {d.right}
          </div>
        );
      })} */}
    </div>
  );
};
