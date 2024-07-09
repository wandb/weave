import {
  MOON_200,
  MOON_700,
  TEAL_500,
  TEAL_600,
} from '@wandb/weave/common/css/color.styles';
import React from 'react';
import {Link as LinkComp, useHistory} from 'react-router-dom';
import styled, {css} from 'styled-components';

import {TargetBlank} from '../../../../../../common/util/links';
import {
  PATH_PARAM,
  usePeekLocation,
  useWeaveflowRouteContext,
} from '../../context';
import {WFHighLevelCallFilter} from '../CallsPage/callsTableFilter';
import {WFHighLevelObjectVersionFilter} from '../ObjectVersionsPage';
import {WFHighLevelOpVersionFilter} from '../OpVersionsPage';
import {Id} from './Id';

type LinkVariant = 'primary' | 'secondary';

type LinkProps = {
  $variant?: LinkVariant;
};

export const A = styled.a<LinkProps>`
  font-weight: 600;
  color: ${p => (p.$variant === 'secondary' ? MOON_700 : TEAL_600)};
  &:hover {
    color: ${TEAL_500};
  }
`;
A.displayName = 'S.A';

export const Link = styled(LinkComp)<LinkProps>`
  font-weight: 600;
  color: ${p => (p.$variant === 'secondary' ? MOON_700 : TEAL_600)};
  &:hover {
    color: ${TEAL_500};
  }
`;
Link.displayName = 'S.Link';

const LinkWrapper = styled.div<{fullWidth?: boolean; color?: string}>`
  ${p =>
    p.fullWidth &&
    css`
      width: 100%;
    `};
  & a {
    color: ${p => p.color ?? 'inherit'};
  }
  & > .callId {
    background-color: ${MOON_200};
    color: ${p => p.color ?? 'inherit'};
  }

  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 2px;
  &:hover {
    & a {
      color: ${TEAL_500};
    }
    & > .callId {
      background-color: ${MOON_200};
      color: ${TEAL_500};
    }
  }
`;
LinkWrapper.displayName = 'S.LinkWrapper';

const LinkTruncater = styled.div<{fullWidth?: boolean}>`
  ${p =>
    p.fullWidth &&
    css`
      flex: 1 1 auto;
    `};

  text-overflow: ellipsis;
  overflow: hidden;
`;
LinkTruncater.displayName = 'S.LinkTruncater';

export const docUrl = (path: string): string => {
  return 'https://wandb.github.io/weave/' + path;
};

export const DocLink = (props: {path: string; text: string}) => {
  return <TargetBlank href={docUrl(props.path)}>{props.text}</TargetBlank>;
};

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
  filePath?: string;
  refExtra?: string;
  fullWidth?: boolean;
  icon?: React.ReactNode;
  color?: string;
}> = props => {
  const history = useHistory();
  const {peekingRouter} = useWeaveflowRouteContext();
  // const text = props.hideName
  //   ? props.version
  //   : props.objectName + ': ' + truncateID(props.version);
  const text = objectVersionText(props.objectName, props.versionIndex);
  const to = peekingRouter.objectVersionUIUrl(
    props.entityName,
    props.projectName,
    props.objectName,
    props.version,
    props.filePath,
    props.refExtra
  );
  const onClick = () => {
    history.push(to);
  };

  return (
    <LinkWrapper
      onClick={onClick}
      fullWidth={props.fullWidth}
      color={props.color}>
      <LinkTruncater fullWidth={props.fullWidth}>
        <Link
          to={to}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}>
          {props.icon}
          {text}
        </Link>
      </LinkTruncater>
    </LinkWrapper>
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
  variant?: LinkVariant;
  fullWidth?: boolean;
}> = props => {
  const history = useHistory();
  const {peekingRouter} = useWeaveflowRouteContext();
  // const text = props.hideName
  //   ? props.version
  //   : props.opName + ': ' + truncateID(props.version);
  const text = opVersionText(props.opName, props.versionIndex);
  const to = peekingRouter.opVersionUIUrl(
    props.entityName,
    props.projectName,
    props.opName,
    props.version
  );
  const onClick = () => {
    history.push(to);
  };
  return (
    <LinkWrapper onClick={onClick} fullWidth={props.fullWidth}>
      <LinkTruncater fullWidth={props.fullWidth}>
        <Link $variant={props.variant} to={to}>
          {text}
        </Link>
      </LinkTruncater>
    </LinkWrapper>
  );
};

export const CallLink: React.FC<{
  entityName: string;
  projectName: string;
  opName: string;
  callId: string;
  variant?: LinkVariant;
  fullWidth?: boolean;
  preservePath?: boolean;
  tracetree?: boolean;
  icon?: React.ReactNode;
  color?: string;
}> = props => {
  const history = useHistory();
  const {peekingRouter} = useWeaveflowRouteContext();
  const opName = opNiceName(props.opName);

  // Custom logic to calculate path and tracetree here is not good. Shows
  // a leak of abstraction. We should not be reaching into the peek location and
  // URL params here. This is a smell that we need to refactor the context
  // to provide the right abstractions.
  const peekLoc = usePeekLocation();
  const peekParams = new URLSearchParams(peekLoc?.search ?? '');
  const existingPath = peekParams.get(PATH_PARAM) ?? '';
  // Preserve the path only when showing trace tree
  const path = props.preservePath ? existingPath : null;

  const to = peekingRouter.callUIUrl(
    props.entityName,
    props.projectName,
    '',
    props.callId,
    path
  );
  const onClick = () => {
    history.push(to);
  };

  return (
    <LinkWrapper
      onClick={onClick}
      fullWidth={props.fullWidth}
      color={props.color}>
      <LinkTruncater fullWidth={props.fullWidth}>
        <Link
          $variant={props.variant}
          to={to}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            justifyContent: 'space-between',
          }}>
          {props.icon}
          {opName}
          <Id id={props.callId} type="Call" />
        </Link>
      </LinkTruncater>
    </LinkWrapper>
  );
};

export const CallsLink: React.FC<{
  entity: string;
  project: string;
  callCount: number;
  countIsLimited?: boolean;
  filter?: WFHighLevelCallFilter;
  neverPeek?: boolean;
  variant?: LinkVariant;
}> = props => {
  const {peekingRouter, baseRouter} = useWeaveflowRouteContext();
  const router = props.neverPeek ? baseRouter : peekingRouter;
  return (
    <Link
      $variant={props.variant}
      to={router.callsUIUrl(props.entity, props.project, props.filter)}>
      {props.callCount}
      {props.countIsLimited ? '+' : ''} calls
    </Link>
  );
};

export const ObjectVersionsLink: React.FC<{
  entity: string;
  project: string;
  versionCount: number;
  countIsLimited?: boolean;
  filter?: WFHighLevelObjectVersionFilter;
  neverPeek?: boolean;
  variant?: LinkVariant;
}> = props => {
  const {peekingRouter, baseRouter} = useWeaveflowRouteContext();
  const router = props.neverPeek ? baseRouter : peekingRouter;
  return (
    <Link
      $variant={props.variant}
      to={router.objectVersionsUIUrl(
        props.entity,
        props.project,
        props.filter
      )}>
      {props.versionCount}
      {props.countIsLimited ? '+' : ''} version
      {props.versionCount !== 1 ? 's' : ''}
    </Link>
  );
};

export const OpVersionsLink: React.FC<{
  entity: string;
  project: string;
  versionCount: number;
  countIsLimited?: boolean;
  filter?: WFHighLevelOpVersionFilter;
  neverPeek?: boolean;
  variant?: LinkVariant;
}> = props => {
  const {peekingRouter, baseRouter} = useWeaveflowRouteContext();
  const router = props.neverPeek ? baseRouter : peekingRouter;
  return (
    <Link
      $variant={props.variant}
      to={router.opVersionsUIUrl(props.entity, props.project, props.filter)}>
      {props.versionCount}
      {props.countIsLimited ? '+' : ''} version
      {props.versionCount !== 1 ? 's' : ''}
    </Link>
  );
};
