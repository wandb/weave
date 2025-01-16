// TODO: Refactor this to be `LLM Judge` tab and change names everywhere

import React from 'react';

import {FilterableObjectVersionsTable} from '../ObjectsPage/ObjectVersionsTable';
export const LLMJudgesTab: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  return (
    <FilterableObjectVersionsTable
      entity={entity}
      project={project}
      hideCategoryColumn
      objectTitle="Scorer"
      initialFilter={{
        // Note: we will need to filter this down to just LLM Judge ActionSpecs, but
        // for now they are the only kind (!!)
        baseObjectClass: 'ActionSpec',
      }}
    />
  );
};
