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
import {ObjectVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';

const Container = styled.div`
  width: 100%;
  height: 100%;
  overflow: hidden;
`;

export const LeaderboardListingPage: React.FC<{
  entity: string;
  project: string;
}> = props => {
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
      headerExtra={<CreateLeaderboardButton />}
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

const CreateLeaderboardButton: FC = () => {
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
        onClick={() => console.log('create leaderboard')}
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
