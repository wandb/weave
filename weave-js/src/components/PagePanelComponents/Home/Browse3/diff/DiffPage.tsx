import React from 'react';

import {DiffPageCalls} from './DiffPageCalls';
import {DiffPageObjects} from './DiffPageObjects';

type DiffPageProps = {
  entity: string;
  project: string;

  diffMode: string;
  setDiffMode: (mode: string) => void;

  calls: string[];
  objects: string[];
  versions: string[];
};

export const DiffPage = ({
  entity,
  project,
  diffMode,
  setDiffMode,
  calls,
  objects,
  versions,
}: DiffPageProps) => {
  if (calls.length > 0) {
    return (
      <DiffPageCalls
        {...{
          entity,
          project,
          diffMode,
          setDiffMode,
          calls,
        }}
      />
    );
  }
  return (
    <DiffPageObjects
      {...{
        entity,
        project,
        diffMode,
        setDiffMode,
        objects,
        versions,
      }}
    />
  );
};
