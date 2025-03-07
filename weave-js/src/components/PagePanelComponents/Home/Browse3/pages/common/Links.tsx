import {GridFilterModel} from '@mui/x-data-grid-pro';
import {
  MOON_200,
  MOON_700,
  TEAL_500,
  TEAL_600,
} from '@wandb/weave/common/css/color.styles';
import {WeaveObjectRef} from '@wandb/weave/react';
import React from 'react';
import {Link as LinkComp} from 'react-router-dom';
import styled, {css} from 'styled-components';

import {TargetBlank} from '../../../../../../common/util/links';
import {maybePluralizeWord} from '../../../../../../core/util/string';
import {
  HIDE_TRACETREE_PARAM,
  SHOW_FEEDBACK_PARAM,
  usePeekLocation,
  useWeaveflowRouteContext,
} from '../../context';
import {WFHighLevelCallFilter} from '../CallsPage/callsTableFilter';
import {WFHighLevelObjectVersionFilter} from '../ObjectsPage/objectsPageTypes';
import {WFHighLevelOpVersionFilter} from '../OpsPage/opsPageTypes';
import {Id} from './Id';
import {opNiceName} from './opNiceName';

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

const FakeLink = styled.div<LinkProps>`
  font-weight: 600;
  color: ${p => (p.$variant === 'secondary' ? MOON_700 : TEAL_600)};
  &:hover {
    color: ${TEAL_500};
  }
`;
FakeLink.displayName = 'S.FakeLink';

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
  hideVersionSuffix?: boolean;
}> = props => {
  const {peekingRouter} = useWeaveflowRouteContext();
  // const text = props.hideName
  //   ? props.version
  //   : props.objectName + ': ' + truncateID(props.version);
  const text = props.hideVersionSuffix
    ? props.objectName
    : objectVersionText(props.objectName, props.versionIndex);
  const to = peekingRouter.objectVersionUIUrl(
    props.entityName,
    props.projectName,
    props.objectName,
    props.version,
    props.filePath,
    props.refExtra
  );

  return (
    <LinkWrapper fullWidth={props.fullWidth} color={props.color}>
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
  color?: string;
}> = props => {
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
  return (
    <LinkWrapper fullWidth={props.fullWidth} color={props.color}>
      <LinkTruncater fullWidth={props.fullWidth}>
        <Link $variant={props.variant} to={to}>
          {text}
        </Link>
      </LinkTruncater>
    </LinkWrapper>
  );
};

export const CallRefLink: React.FC<{
  callRef: WeaveObjectRef;
}> = props => {
  const {peekingRouter} = useWeaveflowRouteContext();
  const callId = props.callRef.artifactName;
  const to = peekingRouter.callUIUrl(
    props.callRef.entityName,
    props.callRef.projectName,
    '',
    callId
  );

  if (props.callRef.weaveKind !== 'call') {
    return null;
  }

  return (
    <LinkWrapper>
      <LinkTruncater>
        <Link
          to={to}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            // allow flex items to shrink below their minimum content size
            minWidth: 0,
          }}>
          <span style={{flexShrink: 0}}>
            <Id id={callId} type="Call" />
          </span>
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
  tracetree?: boolean;
  icon?: React.ReactNode;
  color?: string;
  isEval?: boolean;
}> = props => {
  const {peekingRouter} = useWeaveflowRouteContext();

  const opName = opNiceName(props.opName);

  // Custom logic to calculate path and tracetree here is not good. Shows
  // a leak of abstraction. We should not be reaching into the peek location and
  // URL params here. This is a smell that we need to refactor the context
  // to provide the right abstractions.
  const peekLoc = usePeekLocation();
  const peekParams = new URLSearchParams(peekLoc?.search ?? '');
  // default to true if not specified and not an eval
  const traceTreeParam = peekParams.get(HIDE_TRACETREE_PARAM);
  const hideTraceTree =
    traceTreeParam === '1'
      ? true
      : traceTreeParam === '0'
      ? false
      : props.isEval
      ? true
      : undefined;
  // default to false if not specified
  const showFeedbackParam = peekParams.get(SHOW_FEEDBACK_PARAM);
  const showFeedbackExpand =
    showFeedbackParam === '1'
      ? true
      : showFeedbackParam === '0'
      ? false
      : undefined;
  const to = peekingRouter.callUIUrl(
    props.entityName,
    props.projectName,
    '',
    props.callId,
    undefined,
    hideTraceTree,
    showFeedbackExpand
  );

  return (
    <LinkWrapper fullWidth={props.fullWidth} color={props.color}>
      <LinkTruncater fullWidth={props.fullWidth}>
        <Link
          $variant={props.variant}
          to={to}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            // allow flex items to shrink below their minimum content size
            minWidth: 0,
          }}>
          {props.icon}
          <span
            style={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              flexGrow: 1,
              flexShrink: 1,
            }}>
            {opName}
          </span>
          <span style={{flexShrink: 0}}>
            <Id id={props.callId} type="Call" />
          </span>
        </Link>
      </LinkTruncater>
    </LinkWrapper>
  );
};

export const CustomLink: React.FC<{
  text: string;
  onClick: () => void;
  fullWidth?: boolean;
  color?: string;
  variant?: LinkVariant;
  icon?: React.ReactNode;
}> = props => {
  // Used to look like our other links, but delegate to a custom onClick
  return (
    <LinkWrapper
      onClick={props.onClick}
      fullWidth={props.fullWidth}
      color={props.color}>
      <LinkTruncater fullWidth={props.fullWidth}>
        <FakeLink
          $variant={props.variant}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            // allow flex items to shrink below their minimum content size
            minWidth: 0,
          }}>
          {props.icon}
          <span
            style={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              flexGrow: 1,
              flexShrink: 1,
            }}>
            {props.text}
          </span>
        </FakeLink>
      </LinkTruncater>
    </LinkWrapper>
  );
};

export const CallsLink: React.FC<{
  entity: string;
  project: string;
  callCount?: number;
  countIsLimited?: boolean;
  filter?: WFHighLevelCallFilter;
  gridFilters?: GridFilterModel;
  neverPeek?: boolean;
  variant?: LinkVariant;
}> = props => {
  const {peekingRouter, baseRouter} = useWeaveflowRouteContext();
  const router = props.neverPeek ? baseRouter : peekingRouter;
  let label = 'View Calls';
  if (props.callCount != null) {
    label = props.callCount.toString();
    label += props.countIsLimited ? '+' : '';
    label += ' ';
    label += maybePluralizeWord(props.callCount, 'call');
  }
  return (
    <Link
      $variant={props.variant}
      to={router.callsUIUrl(
        props.entity,
        props.project,
        props.filter,
        props.gridFilters
      )}>
      {label}
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
  children?: React.ReactNode;
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
      {props.children ?? (
        <>
          {props.versionCount}
          {props.countIsLimited ? '+' : ''} version
          {props.versionCount !== 1 ? 's' : ''}
        </>
      )}
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
  children?: React.ReactNode;
}> = props => {
  const {peekingRouter, baseRouter} = useWeaveflowRouteContext();
  const router = props.neverPeek ? baseRouter : peekingRouter;
  return (
    <Link
      $variant={props.variant}
      to={router.opVersionsUIUrl(props.entity, props.project, props.filter)}>
      {props.children ?? (
        <>
          {props.versionCount}
          {props.countIsLimited ? '+' : ''} version
          {props.versionCount !== 1 ? 's' : ''}
        </>
      )}
    </Link>
  );
};
