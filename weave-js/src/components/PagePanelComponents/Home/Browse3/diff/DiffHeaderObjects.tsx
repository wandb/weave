/**
 * Responsible for showing the currently selected objects/versions
 * and letting the user select new ones.
 */

import React from 'react';
import {useHistory, useLocation} from 'react-router-dom';

import {ObjectRef} from '../../../../../react';
import {Button} from '../../../../Button';
import {SmallRef} from '../../Browse2/SmallRef';
import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {
  bringToFront,
  querySetArray,
  querySetString,
  searchParamsSetArray,
} from '../urlQueryUtil';
import {SelectObj} from './SelectObj';
import {SelectObjVersion} from './SelectObjVersion';
import {has} from 'lodash';

type DiffHeaderObjectsProps = {
  objects: ObjectVersionSchema[];
  versionsLeft: ObjectVersionSchema[];
  versionsRight: ObjectVersionSchema[];
  left?: ObjectVersionSchema;
  right?: ObjectVersionSchema;
};

const toObjectRef = (obj: ObjectVersionSchema): ObjectRef => ({
  scheme: 'weave',
  entityName: obj.entity,
  projectName: obj.project,
  weaveKind: 'object',
  artifactName: obj.objectId,
  artifactVersion: obj.versionHash,
});

export const DiffHeaderObjects = ({
  objects,
  versionsLeft,
  versionsRight,
  left,
  right,
}: DiffHeaderObjectsProps) => {
  const {search} = useLocation();
  const history = useHistory();

  const objValueL = left?.objectId ?? '';
  const objValueR = right?.objectId ?? '';
  const objVersionL = left?.versionHash ?? '';
  const objVersionR = right?.versionHash ?? '';
  const hasPrevNext = objValueL === objValueR;
  console.log({hasPrevNext, objValueL, objValueR});
  const versionIndexL = versionsLeft.findIndex(
    v => v.versionHash === objVersionL
  );
  const versionIndexR = versionsRight.findIndex(
    v => v.versionHash === objVersionR
  );

  const onChangeObjL = (id: string): void => {
    const newQuery = new URLSearchParams(search);
    const objects = [id, objValueR];
    searchParamsSetArray(newQuery, 'object', objects);
    history.push({search: newQuery.toString()});
  };
  const onChangeObjR = (id: string): void => {
    const newQuery = new URLSearchParams(search);
    const objects = [objValueL, id];
    searchParamsSetArray(newQuery, 'object', objects);
    history.push({search: newQuery.toString()});
  };

  const onChangeVersionL = (hash: string): void => {
    const newQuery = new URLSearchParams(search);
    const versions = [hash, objVersionR];
    searchParamsSetArray(newQuery, 'version', versions);
    history.push({search: newQuery.toString()});
  };
  const onChangeVersionR = (hash: string): void => {
    const newQuery = new URLSearchParams(search);
    const versions = [objVersionL, hash];
    searchParamsSetArray(newQuery, 'version', versions);
    history.push({search: newQuery.toString()});
  };

  const onClickSwap = () => {
    const newQuery = new URLSearchParams(search);
    searchParamsSetArray(newQuery, 'object', [objValueR, objValueL]);
    searchParamsSetArray(newQuery, 'version', [objVersionR, objVersionL]);
    history.push({search: newQuery.toString()});
  };
  const isSwapDisabled = objValueL === objValueR && objVersionL === objVersionR;

  const onPrev = () => {
    const newQuery = new URLSearchParams(search);
    // TODO: Not click how we should change if difference in index is not currently 1
    const newVersionL = versionsLeft[versionIndexL + 1].versionHash;
    const newVersionR = versionsRight[versionIndexR + 1].versionHash;
    const versions = [newVersionL, newVersionR];
    searchParamsSetArray(newQuery, 'version', versions);
    history.push({search: newQuery.toString()});
  };
  const onNext = () => {
    const newQuery = new URLSearchParams(search);
    const newVersionL = versionsLeft[versionIndexL - 1].versionHash;
    const newVersionR = versionsRight[versionIndexR - 1].versionHash;
    const versions = [newVersionL, newVersionR];
    searchParamsSetArray(newQuery, 'version', versions);
    history.push({search: newQuery.toString()});
  };
  const hasPrev = versionIndexL < versionsLeft.length - 1;
  const hasNext = versionIndexR > 0;

  return (
    <div className="p-8">
      <div className="grid grid-cols-[50px_max-content_auto] content-center items-center gap-x-8 gap-y-4">
        <div>
          <Button
            size="small"
            variant="quiet"
            onClick={onClickSwap}
            disabled={isSwapDisabled}
            icon="retry"
          />
        </div>
        <div>
          {hasPrevNext && (
            <>
              <Button
                disabled={!hasPrev}
                size="small"
                variant="quiet"
                icon="chevron-back"
                onClick={onPrev}
                tooltip="Compare earlier versions"
              />
              <Button
                disabled={!hasNext}
                size="small"
                variant="quiet"
                icon="chevron-next"
                onClick={onNext}
                tooltip="Compare later versions"
              />
            </>
          )}
        </div>
        <div></div>
        <div>Left</div>
        <div className="flex gap-4">
          <SelectObj
            objVersions={objects}
            valueId={objValueL}
            onChange={onChangeObjL}
          />
          {objValueL && (
            <SelectObjVersion
              objVersions={versionsLeft}
              valueHash={objVersionL}
              onChange={onChangeVersionL}
            />
          )}
        </div>
        <div>{left && <SmallRef objRef={toObjectRef(left)} />}</div>
        <div>Right</div>
        <div className="flex gap-4">
          <SelectObj
            objVersions={objects}
            valueId={objValueL}
            onChange={onChangeObjR}
          />
          {objValueR && (
            <SelectObjVersion
              objVersions={versionsRight}
              valueHash={objVersionR}
              onChange={onChangeVersionR}
            />
          )}
        </div>
        <div>{right && <SmallRef objRef={toObjectRef(right)} />}</div>
      </div>
    </div>
  );
};
