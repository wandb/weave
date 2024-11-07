/**
 * Handle loading object data.
 */
import React from 'react';

import {LoadingDots} from '../../../../LoadingDots';
import {ComparePageObjectsLoaded} from './ComparePageObjectsLoaded';
import {useObjectVersions} from './hooks';
import {Mode} from './types';

type ComparePageObjectsProps = {
  entity: string;
  project: string;
  objectIds: string[];
  mode: Mode;
  baselineEnabled: boolean;
  onlyChanged: boolean;
};

export const ComparePageObjects = (props: ComparePageObjectsProps) => {
  const {entity, project, objectIds} = props;
  const {loading, objectVersions, lastVersionIndices} = useObjectVersions(
    entity,
    project,
    objectIds
  );
  if (loading) {
    return <LoadingDots />;
  }

  return (
    <ComparePageObjectsLoaded
      {...props}
      objectType="object"
      objects={objectVersions}
      lastVersionIndices={lastVersionIndices}
    />
  );
};
