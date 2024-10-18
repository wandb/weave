import {Box} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button/Button';
import React, {FC, useCallback} from 'react';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import {useWeaveflowRouteContext} from '../../context';
import {StyledDataGrid} from '../../StyledDataGrid';
import {CallsTable} from '../CallsPage/CallsTable';
import {useEvaluationsFilter} from '../CallsPage/evaluationsFilter';
import {Empty} from '../common/Empty';
import {
  EMPTY_PROPS_EVALUATIONS,
  EMPTY_PROPS_LEADERBOARDS,
} from '../common/EmptyContent';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {
  FilterableObjectVersionsTable,
  ObjectVersionsTable,
} from '../ObjectVersionsPage';
import {useWFHooks} from '../wfReactInterface/context';
import {ObjectVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';

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
  // const customLeaderboards = [
  //   {
  //     name: 'Weather_genApp_experts',
  //     description: 'This is the description',
  //     modelsEvaluated: '16',
  //   },
  //   {
  //     name: 'TidePressure_modeling_team',
  //     description: 'This is the description',
  //     modelsEvaluated: '30',
  //   },
  //   {
  //     name: 'ClimateModel_genApp_experts',
  //     description: 'This is the description',
  //     modelsEvaluated: '15',
  //   },
  //   {
  //     name: 'OceanCurrent_analysis_team',
  //     description: 'This is the description',
  //     modelsEvaluated: '70',
  //   },
  //   {
  //     name: 'Windflow_projection_experts',
  //     description: 'This is the description',
  //     modelsEvaluated: '82',
  //   },
  //   {
  //     name: 'AtmoMetrics_analysis_team',
  //     description: 'This is the description',
  //     modelsEvaluated: '40',
  //   },
  //   {
  //     name: 'HydroFluor_research_specialists',
  //     description: 'This is the description',
  //     modelsEvaluated: '202',
  //   },
  // ];

  // const evalBoards = [
  //   {
  //     name: 'Weather_genApp_experts',
  //     description: 'This is the description',
  //     modelsEvaluated: '16',
  //   },
  //   {
  //     name: 'TidePressure_modeling_team',
  //     description: 'This is the description',
  //     modelsEvaluated: '30',
  //   },
  //   {
  //     name: 'ClimateModel_genApp_experts',
  //     description: 'This is the description',
  //     modelsEvaluated: '15',
  //   },
  //   {
  //     name: 'OceanCurrent_analysis_team',
  //     description: 'This is the description',
  //     modelsEvaluated: '70',
  //   },
  //   {
  //     name: 'Windflow_projection_experts',
  //     description: 'This is the description',
  //     modelsEvaluated: '82',
  //   },
  //   {
  //     name: 'AtmoMetrics_analysis_team',
  //     description: 'This is the description',
  //     modelsEvaluated: '40',
  //   },
  //   {
  //     name: 'HydroFluor_research_specialists',
  //     description: 'This is the description',
  //     modelsEvaluated: '202',
  //   },
  // ];

  // const hasCustomLeaderboards = customLeaderboards.length > 0;
  // const hasEvalLeaderboards = evalBoards.length > 0;
  // const allEmpty = !hasCustomLeaderboards && !hasEvalLeaderboards;
  const evaluationsFilter = useEvaluationsFilter(props.entity, props.project);

  return (
    <Container>
      <Section>
        {/* <SectionTitle>Leaderboards</SectionTitle> */}
        <LeaderboardTable entity={props.entity} project={props.project} />
        {/* // <QueueGrid>
          //   {customLeaderboards.map(queue => (
          //     <QueueCard key={queue.name}>
          //       <LeaderboardName>{queue.name}</LeaderboardName>
          //       <LeaderboardDescription>{queue.description}</LeaderboardDescription>
          //       <ModelCount>
          //         {queue.modelsEvaluated} models
          //       </ModelCount>
          //     </QueueCard>
          //   ))}
          // </QueueGrid>
        )} */}
      </Section>
      <Section>
        <SectionTitle>Recent Evaluations</SectionTitle>
        {/* <CallsTable 
            entity={props.entity}
            project={props.project}
            frozenFilter={evaluationsFilter}
            // hideControls
            // hideOpSelector
            allowedColumnPatterns={['status','inputs.self', 'inputs.model', 'output.*']}
          /> */}
        {/* <QueueGrid>
          {evalBoards.map(queue => (
            <QueueCard key={queue.name}>
              <LeaderboardName>{queue.name}</LeaderboardName>
              <LeaderboardDescription>{queue.description}</LeaderboardDescription>
              <ModelCount>
                {queue.modelsEvaluated} models
              </ModelCount>
            </QueueCard>
          ))}
        </QueueGrid> */}
      </Section>
    </Container>
  );
};

const Container = styled.div`
  // padding: 16px;
  width: 100%;
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
`;

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
        onClick={console.log}
        icon="add-new">
        Create Leaderboard
      </Button>
    </Box>
  );
};

const Section = styled.div`
  margin-top: 0px;
  margin-bottom: 30px;
  flex: 1;
  overflow: hidden;
`;

const SectionTitle = styled.h2`
  font-size: 18px;
  margin-bottom: 10px;
`;

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
