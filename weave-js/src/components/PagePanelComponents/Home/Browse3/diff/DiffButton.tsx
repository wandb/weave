/**
 * This is a button that takes you to the diff page.
 */

import React from 'react';
import {useHistory} from 'react-router-dom';

import {Button} from '../../../../Button';
import {useWeaveflowCurrentRouteContext} from '../context';

type DiffButtonProps = {
  entity: string;
  project: string;

  calls?: string[];

  objectIds?: string[];
  versions?: string[];
};

export const DiffButton = ({
  entity,
  project,
  calls,
  objectIds,
  versions,
}: DiffButtonProps) => {
  const routerContext = useWeaveflowCurrentRouteContext();
  const history = useHistory();

  const onClick = () => {
    history.push(
      routerContext.diffUrl(entity, project, {
        call: calls,
        object: objectIds,
        version: versions,
      })
    );
  };
  return (
    <Button
      size="small"
      variant="ghost"
      icon="pan-tool-1"
      tooltip="Compare this object"
      onClick={onClick}
    />
  );
};
