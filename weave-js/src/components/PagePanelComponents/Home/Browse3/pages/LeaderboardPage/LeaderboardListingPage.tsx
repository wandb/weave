import {Box} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button/Button';
import {ErrorPanel} from '@wandb/weave/components/ErrorPanel';
import {Loading} from '@wandb/weave/components/Loading';
import React, {FC, useCallback} from 'react';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import {useWeaveflowRouteContext} from '../../context';
import {Empty} from '../common/Empty';
import {EMPTY_PROPS_LEADERBOARDS} from '../common/EmptyContent';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {ObjectVersionsTable} from '../ObjectVersionsPage';
import {useWFHooks} from '../wfReactInterface/context';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {sanitizeObjectId} from '../wfReactInterface/traceServerDirectClient';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {ObjectVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {useIsEditor} from './LeaderboardPage';

const Container = styled.div`
  width: 100%;
  height: 100%;
  overflow: hidden;
`;

export const LeaderboardListingPage: React.FC<{
  entity: string;
  project: string;
}> = props => {
  const {isEditor} = useIsEditor(props.entity);
  return (
    <SimplePageLayout
      title={`Leaderboards`}
      hideTabsIfSingle
      tabs={[
        {
          label: 'All',
          content: <LeaderboardListingPageInner {...props} />,
        },
      ]}
      headerExtra={
        isEditor && (
          <CreateLeaderboardButton
            entity={props.entity}
            project={props.project}
          />
        )
      }
    />
  );
};

export const LeaderboardListingPageInner: React.FC<{
  entity: string;
  project: string;
}> = props => {
  return (
    <Container>
      <LeaderboardTable entity={props.entity} project={props.project} />
    </Container>
  );
};

const CreateLeaderboardButton: FC<{
  entity: string;
  project: string;
}> = props => {
  const createLeaderboard = useCreateLeaderboard(props.entity, props.project);
  const navigateToLeaderboard = useNavigateToLeaderboard(
    props.entity,
    props.project
  );
  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
      }}>
      <Button
        className="mx-16"
        style={{
          marginLeft: '0px',
        }}
        size="medium"
        variant="secondary"
        onClick={() => {
          createLeaderboard().then(navigateToLeaderboard);
        }}
        icon="add-new">
        Create Leaderboard
      </Button>
    </Box>
  );
};

const LeaderboardTable: React.FC<{
  entity: string;
  project: string;
}> = props => {
  const history = useHistory();
  const {peekingRouter} = useWeaveflowRouteContext();
  const {useRootObjectVersions} = useWFHooks();

  // TODO: Once `useCollectionObjects` lands from the online
  // evals project, switch to that (much more type safe)
  const leaderboardObjectVersions = useRootObjectVersions(
    props.entity,
    props.project,
    {
      baseObjectClasses: ['Leaderboard'],
      latestOnly: true,
    }
  );
  const onClick = useCallback(
    (obj: ObjectVersionSchema) => {
      const to = peekingRouter.leaderboardsUIUrl(
        props.entity,
        props.project,
        obj.objectId
      );
      history.push(to);
    },
    [history, peekingRouter, props.entity, props.project]
  );

  if (leaderboardObjectVersions.loading) {
    return <Loading centered />;
  }
  if (leaderboardObjectVersions.error) {
    return <ErrorPanel />;
  }

  const objectVersions = leaderboardObjectVersions.result ?? [];
  const isEmpty = objectVersions.length === 0;
  if (isEmpty) {
    return <Empty {...EMPTY_PROPS_LEADERBOARDS} />;
  }

  return (
    <ObjectVersionsTable
      objectVersions={leaderboardObjectVersions.result ?? []}
      objectTitle="Name"
      hidePropsAsColumns
      hidePeerVersionsColumn
      hideCategoryColumn
      hideVersionSuffix
      onRowClick={onClick}
    />
  );
};

const generateLeaderboardId = () => {
  const timestamp = new Date().getTime();
  const timestampHex = timestamp.toString(36);
  return `leaderboard-${timestampHex}`;
};

const useCreateLeaderboard = (entity: string, project: string) => {
  const getTsClient = useGetTraceServerClientContext();
  const client = getTsClient();

  // TODO: Once `useCreateCollectionObject` lands from the online
  // evals project, switch to that (much more type safe)
  const createLeaderboard = async () => {
    const objectId = sanitizeObjectId(generateLeaderboardId());
    await client.objCreate({
      obj: {
        project_id: projectIdFromParts({entity, project}),
        object_id: objectId,
        val: {
          _type: 'Leaderboard',
          _class_name: 'Leaderboard',
          _bases: ['Object', 'BaseModel'],
          name: objectId,
          description: '',
          columns: [],
        },
      },
    });
    return objectId;
  };

  return createLeaderboard;
};

const useNavigateToLeaderboard = (entity: string, project: string) => {
  const history = useHistory();
  const {baseRouter} = useWeaveflowRouteContext();
  const navigateToLeaderboard = useCallback(
    (objectId: string) => {
      const to = baseRouter.leaderboardsUIUrl(entity, project, objectId, true);
      history.push(to);
    },
    [history, baseRouter, entity, project]
  );
  return navigateToLeaderboard;
};
