import React from 'react';
import {Link} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../../context';
import {WFHighLevelCallFilter} from '../CallsPage';
import {WFHighLevelObjectVersionFilter} from '../ObjectVersionsPage';
import {WFHighLevelOpVersionFilter} from '../OpVersionsPage';
import {WFHighLevelTypeVersionFilter} from '../TypeVersionsPage';

export const TypeLink: React.FC<{
  entityName: string;
  projectName: string;
  typeName: string;
}> = props => {
  const {peekingRouter} = useWeaveflowRouteContext();
  return (
    <Link
      to={peekingRouter.typeUIUrl(
        props.entityName,
        props.projectName,
        props.typeName
      )}>
      {props.typeName}
    </Link>
  );
};

export const TypeVersionLink: React.FC<{
  entityName: string;
  projectName: string;
  typeName: string;
  version: string;
  hideName?: boolean;
}> = props => {
  const {peekingRouter} = useWeaveflowRouteContext();
  const text = props.hideName
    ? props.version
    : props.typeName + ': ' + props.version;
  return (
    <Link
      to={peekingRouter.typeVersionUIUrl(
        props.entityName,
        props.projectName,
        props.typeName,
        props.version
      )}>
      {text}
    </Link>
  );
};

export const ObjectLink: React.FC<{
  entityName: string;
  projectName: string;
  objectName: string;
}> = props => {
  const {peekingRouter} = useWeaveflowRouteContext();
  return (
    <Link
      to={peekingRouter.objectUIUrl(
        props.entityName,
        props.projectName,
        props.objectName
      )}>
      {props.objectName}
    </Link>
  );
};

export const ObjectVersionLink: React.FC<{
  entityName: string;
  projectName: string;
  objectName: string;
  version: string;
  hideName?: boolean;
}> = props => {
  const {peekingRouter} = useWeaveflowRouteContext();
  const text = props.hideName
    ? props.version
    : props.objectName + ': ' + props.version;
  return (
    <Link
      to={peekingRouter.objectVersionUIUrl(
        props.entityName,
        props.projectName,
        props.objectName,
        props.version
      )}>
      {text}
    </Link>
  );
};

export const OpLink: React.FC<{
  entityName: string;
  projectName: string;
  opName: string;
}> = props => {
  const {peekingRouter} = useWeaveflowRouteContext();
  return (
    <Link
      to={peekingRouter.opUIUrl(
        props.entityName,
        props.projectName,
        props.opName
      )}>
      {props.opName}
    </Link>
  );
};

export const OpVersionLink: React.FC<{
  entityName: string;
  projectName: string;
  opName: string;
  version: string;
  hideName?: boolean;
}> = props => {
  const {peekingRouter} = useWeaveflowRouteContext();
  const text = props.hideName
    ? props.version
    : props.opName + ': ' + props.version;
  return (
    <Link
      to={peekingRouter.opVersionUIUrl(
        props.entityName,
        props.projectName,
        props.opName,
        props.version
      )}>
      {text}
    </Link>
  );
};

export const CallLink: React.FC<{
  entityName: string;
  projectName: string;
  callId: string;
}> = props => {
  const {peekingRouter} = useWeaveflowRouteContext();

  return (
    <Link
      to={peekingRouter.callUIUrl(
        props.entityName,
        props.projectName,
        '',
        props.callId
      )}>
      {props.callId}
    </Link>
  );
};

export const CallsLink: React.FC<{
  entity: string;
  project: string;
  callCount: number;
  filter?: WFHighLevelCallFilter;
}> = props => {
  const {peekingRouter} = useWeaveflowRouteContext();
  return (
    <Link
      to={peekingRouter.callsUIUrl(props.entity, props.project, props.filter)}>
      {props.callCount} calls
    </Link>
  );
};

export const ObjectVersionsLink: React.FC<{
  entity: string;
  project: string;
  versionsCount: number;
  filter?: WFHighLevelObjectVersionFilter;
}> = props => {
  const {peekingRouter} = useWeaveflowRouteContext();
  return (
    <Link
      to={peekingRouter.objectVersionsUIUrl(
        props.entity,
        props.project,
        props.filter
      )}>
      {props.versionsCount} objects
    </Link>
  );
};

export const OpVersionsLink: React.FC<{
  entity: string;
  project: string;
  versionCount: number;
  filter?: WFHighLevelOpVersionFilter;
}> = props => {
  const {peekingRouter} = useWeaveflowRouteContext();
  return (
    <Link
      to={peekingRouter.opVersionsUIUrl(
        props.entity,
        props.project,
        props.filter
      )}>
      {props.versionCount} versions
    </Link>
  );
};

export const TypeVersionsLink: React.FC<{
  entity: string;
  project: string;
  versionCount: number;
  filter?: WFHighLevelTypeVersionFilter;
}> = props => {
  const {peekingRouter} = useWeaveflowRouteContext();
  return (
    <Link
      to={peekingRouter.typeVersionsUIUrl(
        props.entity,
        props.project,
        props.filter
      )}>
      {props.versionCount} versions
    </Link>
  );
};
