/**
 * Responsible for showing the currently selected objects/versions
 * and letting the user select new ones.
 */

import React from 'react';
import {useHistory, useLocation} from 'react-router-dom';

import {queryGetDict} from '../urlQueryUtil';
import {SelectCall} from './SelectCall';

type DiffHeaderCallsProps = {
  calls: string[];
  left: string;
  right: string;
};

export const DiffHeaderCalls = ({calls, left, right}: DiffHeaderCallsProps) => {
  const {search} = useLocation();
  const history = useHistory();

  const onChangeL = (id: string): void => {
    // Bring to front
    const newCalls = [id].concat(calls.filter(call => call !== id));
    const newQuery = new URLSearchParams(search);
    newQuery.delete('call');
    newCalls.forEach(call => {
      newQuery.append('call', call);
    });
    history.push({search: newQuery.toString()});
  };
  const onChangeR = (id: string): void => {
    // TODO
    // const newQuery = new URLSearchParams(search);
    // newQuery.set('call2', id);
    // history.replace({search: newQuery.toString()});
  };

  return (
    <div className="p-8">
      <div className="grid grid-cols-[50px_auto] content-center items-center gap-x-8 gap-y-4">
        <div>Left</div>
        <div className="flex gap-4">
          <SelectCall calls={calls} valueId={left} onChange={onChangeL} />
        </div>
        <div>Right</div>
        <div className="flex gap-4">
          <SelectCall calls={calls} valueId={right} onChange={onChangeR} />
        </div>
      </div>
    </div>
  );
};
