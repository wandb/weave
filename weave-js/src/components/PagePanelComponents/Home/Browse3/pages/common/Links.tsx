import React from 'react';
import {Link} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../../context';
import {WFHighLevelCallFilter} from '../CallsPage';
import {useWeaveflowORMContext} from '../interface/wf/context';
import {WFHighLevelObjectVersionFilter} from '../ObjectVersionsPage';
import {WFHighLevelOpVersionFilter} from '../OpVersionsPage';
import {WFHighLevelTypeVersionFilter} from '../TypeVersionsPage';

export const TypeLink: React.FC<{typeName: string}> = props => {
  const orm = useWeaveflowORMContext();
  const routerContext = useWeaveflowRouteContext();
  try {
    const type = orm.projectConnection.type(props.typeName);
    return (
      <Link
        to={routerContext.typeUIUrl(
          type.entity(),
          type.project(),
          type.name()
        )}>
        {props.typeName}
      </Link>
    );
  } catch (e) {
    return <span>{props.typeName}</span>;
  }
};

export const TypeVersionLink: React.FC<{
  typeName: string;
  version: string;
  hideName?: boolean;
}> = props => {
  const orm = useWeaveflowORMContext();
  const routerContext = useWeaveflowRouteContext();
  const text = props.hideName
    ? props.version
    : props.typeName + ': ' + props.version;
  try {
    const typeVersion = orm.projectConnection.typeVersion(
      props.typeName,
      props.version
    );
    return (
      <Link
        to={routerContext.typeVersionUIUrl(
          typeVersion.entity(),
          typeVersion.project(),
          typeVersion.type().name(),
          typeVersion.version()
        )}>
        {text}
      </Link>
    );
  } catch (e) {
    console.error(e);
    return <span>{text}</span>;
  }
};

export const ObjectLink: React.FC<{objectName: string}> = props => {
  const orm = useWeaveflowORMContext();
  const routerContext = useWeaveflowRouteContext();
  try {
    const object = orm.projectConnection.object(props.objectName);
    return (
      <Link
        to={routerContext.objectUIUrl(
          object.entity(),
          object.project(),
          object.name()
        )}>
        {props.objectName}
      </Link>
    );
  } catch (e) {
    return <span>{props.objectName}</span>;
  }
};

export const ObjectVersionLink: React.FC<{
  objectName: string;
  version: string;
  hideName?: boolean;
}> = props => {
  const orm = useWeaveflowORMContext();
  const routerContext = useWeaveflowRouteContext();
  const text = props.hideName
    ? props.version
    : props.objectName + ': ' + props.version;
  try {
    const objectVersion = orm.projectConnection.objectVersion(
      props.objectName,
      props.version
    );
    return (
      <Link
        to={routerContext.objectVersionUIUrl(
          objectVersion.entity(),
          objectVersion.project(),
          objectVersion.object().name(),
          objectVersion.version()
        )}>
        {text}
      </Link>
    );
  } catch (e) {
    return <span>{text}</span>;
  }
};

export const OpLink: React.FC<{opName: string}> = props => {
  const orm = useWeaveflowORMContext();
  const routerContext = useWeaveflowRouteContext();
  try {
    const op = orm.projectConnection.op(props.opName);
    return (
      <Link to={routerContext.opUIUrl(op.entity(), op.project(), op.name())}>
        {props.opName}
      </Link>
    );
  } catch (e) {
    return <span>{props.opName}</span>;
  }
};

export const OpVersionLink: React.FC<{
  opName: string;
  version: string;
  hideName?: boolean;
}> = props => {
  const orm = useWeaveflowORMContext();
  const routerContext = useWeaveflowRouteContext();
  const text = props.hideName
    ? props.version
    : props.opName + ': ' + props.version;
  try {
    const opVersion = orm.projectConnection.opVersion(
      props.opName,
      props.version
    );
    return (
      <Link
        to={routerContext.opVersionUIUrl(
          opVersion.entity(),
          opVersion.project(),
          opVersion.op().name(),
          opVersion.version()
        )}>
        {text}
      </Link>
    );
  } catch (e) {
    return <span>{text}</span>;
  }
};

export const CallLink: React.FC<{callId: string}> = props => {
  const orm = useWeaveflowORMContext();
  const routerContext = useWeaveflowRouteContext();

  const call = orm.projectConnection.call(props.callId);
  let callName = call.callID();
  const callOpVersion = call.opVersion();
  if (callOpVersion) {
    callName = callOpVersion.op().name() + ' : ' + callOpVersion.version();
  }
  return (
    <Link
      to={routerContext.callUIUrl(
        call.entity(),
        call.project(),
        call.traceID(),
        call.callID()
      )}>
      {callName}
    </Link>
  );
};

export const CallsLink: React.FC<{
  entity: string;
  project: string;
  callCount: number;
  filter?: WFHighLevelCallFilter;
}> = props => {
  const routerContext = useWeaveflowRouteContext();
  return (
    <Link
      to={routerContext.callsUIUrl(props.entity, props.project, props.filter)}>
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
  const routerContext = useWeaveflowRouteContext();
  return (
    <Link
      to={routerContext.objectVersionsUIUrl(
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
  const routerContext = useWeaveflowRouteContext();
  return (
    <Link
      to={routerContext.opVersionsUIUrl(
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
  const routerContext = useWeaveflowRouteContext();
  return (
    <Link
      to={routerContext.typeVersionsUIUrl(
        props.entity,
        props.project,
        props.filter
      )}>
      {props.versionCount} versions
    </Link>
  );
};
