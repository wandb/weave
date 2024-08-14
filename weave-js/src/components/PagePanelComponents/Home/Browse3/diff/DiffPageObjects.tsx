import _ from 'lodash';
import React from 'react';

import {Loading} from '../../../../Loading';
import {Tailwind} from '../../../../Tailwind';
import {SimplePageLayout} from '../pages/common/SimplePageLayout';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {DiffHeaderObjects} from './DiffHeaderObjects';
import {ObjectDiffSelector} from './ObjectDiffSelector';

type DiffPageObjectsProps = {
  entity: string;
  project: string;

  diffMode: string;
  setDiffMode: (mode: string) => void;

  objects: string[];
  versions: string[];
};

export const DiffPageObjects = ({
  entity,
  project,
  diffMode,
  setDiffMode,
  objects,
  versions,
}: DiffPageObjectsProps) => {
  const {useRootObjectVersions} = useWFHooks();

  // TODO: We should add a parameter to this API to not get the values.
  const knownObjects = useRootObjectVersions(entity, project, {
    latestOnly: true,
  });

  const objectVersions = useRootObjectVersions(entity, project, {
    objectIds: objects, // OK if these values are the same.
  });

  if (knownObjects.loading || objectVersions.loading) {
    return <Loading />;
  }

  const loadedObjects = knownObjects.result ?? [];
  const grouped = _.groupBy(objectVersions.result, v => v.objectId);

  const objectIdL = objects[0] ?? '';
  const objectIdR = objects[1] ?? objectIdL;
  let versionL = versions[0] ?? '';
  let versionR = versions[1] ?? versionL;
  if (objects.length === 1) {
    // We want to look at two versions of the same object.
    if (versions.length === 1) {
      const availableVersions = grouped[objectIdL] ?? [];
      const nAvailable = availableVersions.length;
      const idx = availableVersions.findIndex(v => v.versionHash === versionL);
      if (nAvailable > 1) {
        if (idx === 0) {
          versionR = availableVersions[1].versionHash;
        } else {
          versionL = availableVersions[idx - 1].versionHash;
        }
      }
    }
  }

  const versionsL = _.orderBy(grouped[objectIdL] ?? [], 'versionIndex', 'desc');
  const versionsR = _.orderBy(grouped[objectIdR] ?? [], 'versionIndex', 'desc');

  // if (versionsL.length === 0) {
  //   return <div>No versions found for: {objectIdL}</div>;
  // }
  // if (versionsR.length === 0) {
  //   return <div>No versions found for: {objectIdR}</div>;
  // }

  const left = _.find(versionsL, v => v.versionHash === versionL);
  const right = _.find(versionsR, v => v.versionHash === versionR);

  let diffBody = null;
  if (versionsL.length > 0) {
    diffBody = (
      <ObjectDiffSelector
        objectType="object"
        diffMode={diffMode}
        setDiffMode={setDiffMode}
        left={left}
        right={right}
      />
    );
  }

  return (
    <SimplePageLayout
      title="Compare objects"
      hideTabsIfSingle
      tabs={[
        {
          label: '',
          content: (
            <Tailwind style={{display: 'contents'}}>
              <DiffHeaderObjects
                objects={loadedObjects}
                versionsLeft={versionsL}
                versionsRight={versionsR}
                left={left}
                right={right}
              />
              {diffBody}
            </Tailwind>
          ),
        },
      ]}
    />
  );
};
