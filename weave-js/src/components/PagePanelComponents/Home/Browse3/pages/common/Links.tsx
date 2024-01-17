import React from 'react';
import {Link} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../../context';
import {WFHighLevelCallFilter} from '../CallsPage';
import {WFHighLevelObjectVersionFilter} from '../ObjectVersionsPage';
import {WFHighLevelOpVersionFilter} from '../OpVersionsPage';
import {WFHighLevelTypeVersionFilter} from '../TypeVersionsPage';
import {truncateID} from '../util';

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
    : props.typeName + ': ' + truncateID(props.version);
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

export const objectVersionText = (opName: string, versionIndex: number) => {
  let text = opName;
  text += ':v' + versionIndex;
  return text;
};

export const ObjectVersionLink: React.FC<{
  entityName: string;
  projectName: string;
  objectName: string;
  version: string;
  versionIndex: number;
}> = props => {
  const {peekingRouter} = useWeaveflowRouteContext();
  // const text = props.hideName
  //   ? props.version
  //   : props.objectName + ': ' + truncateID(props.version);
  const text = objectVersionText(props.objectName, props.versionIndex);
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

export const opNiceName = (opName: string) => {
  let text = opName;
  if (text.startsWith('op-')) {
    text = text.slice(3);
  }
  return text;
};

export const opVersionText = (opName: string, versionIndex: number) => {
  let text = opNiceName(opName);
  text += ':v' + versionIndex;
  return text;
};

export const OpVersionLink: React.FC<{
  entityName: string;
  projectName: string;
  opName: string;
  version: string;
  versionIndex: number;
}> = props => {
  const {peekingRouter} = useWeaveflowRouteContext();
  // const text = props.hideName
  //   ? props.version
  //   : props.opName + ': ' + truncateID(props.version);
  const text = opVersionText(props.opName, props.versionIndex);
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
  simpleText?: {
    opName: string;
    versionIndex: number;
  };
}> = props => {
  const {peekingRouter} = useWeaveflowRouteContext();
  let text = truncateID(props.callId);
  if (props.simpleText) {
    text = opVersionText(
      props.simpleText.opName,
      props.simpleText.versionIndex
    );
  }
  return (
    <Link
      to={peekingRouter.callUIUrl(
        props.entityName,
        props.projectName,
        '',
        props.callId
      )}>
      {text}
    </Link>
  );
};

export const CallsLink: React.FC<{
  entity: string;
  project: string;
  callCount: number;
  filter?: WFHighLevelCallFilter;
  neverPeek?: boolean;
}> = props => {
  const {peekingRouter, baseRouter} = useWeaveflowRouteContext();
  const router = props.neverPeek ? baseRouter : peekingRouter;
  return (
    <Link to={router.callsUIUrl(props.entity, props.project, props.filter)}>
      {props.callCount} calls
    </Link>
  );
};

export const ObjectVersionsLink: React.FC<{
  entity: string;
  project: string;
  versionCount: number;
  filter?: WFHighLevelObjectVersionFilter;
  neverPeek?: boolean;
}> = props => {
  const {peekingRouter, baseRouter} = useWeaveflowRouteContext();
  const router = props.neverPeek ? baseRouter : peekingRouter;
  return (
    <Link
      to={router.objectVersionsUIUrl(
        props.entity,
        props.project,
        props.filter
      )}>
      {props.versionCount} version{props.versionCount !== 1 ? 's' : ''}
    </Link>
  );
};

export const OpVersionsLink: React.FC<{
  entity: string;
  project: string;
  versionCount: number;
  filter?: WFHighLevelOpVersionFilter;
  neverPeek?: boolean;
}> = props => {
  const {peekingRouter, baseRouter} = useWeaveflowRouteContext();
  const router = props.neverPeek ? baseRouter : peekingRouter;
  return (
    <Link
      to={router.opVersionsUIUrl(props.entity, props.project, props.filter)}>
      {props.versionCount} version{props.versionCount !== 1 ? 's' : ''}
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
      {props.versionCount} version{props.versionCount !== 1 ? 's' : ''}
    </Link>
  );
};
