import React from 'react';
import {Link} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../../context';
import {useWeaveflowORMContext} from '../interface/wf/context';

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
