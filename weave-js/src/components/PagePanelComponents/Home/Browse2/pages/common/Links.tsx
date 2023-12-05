import React from 'react';
import {Link} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../../context';
import {useWeaveflowORMContext} from '../interface/wf/context';
import {WFHighLevelCallFilter} from '../CallsPage';

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
}> = props => {
  const orm = useWeaveflowORMContext();
  const routerContext = useWeaveflowRouteContext();
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
        {props.typeName} : {props.version}
      </Link>
    );
  } catch (e) {
    return (
      <span>
        {props.typeName} : {props.version}
      </span>
    );
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
}> = props => {
  const orm = useWeaveflowORMContext();
  const routerContext = useWeaveflowRouteContext();
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
        {props.objectName} : {props.version}
      </Link>
    );
  } catch (e) {
    return (
      <span>
        {props.objectName}: {props.version}
      </span>
    );
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
}> = props => {
  const orm = useWeaveflowORMContext();
  const routerContext = useWeaveflowRouteContext();
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
        {props.opName} : {props.version}
      </Link>
    );
  } catch (e) {
    return (
      <span>
        {props.opName}: {props.version}
      </span>
    );
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
