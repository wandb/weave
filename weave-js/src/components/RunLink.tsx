/**
 * Show information about one W&B Run.
 */

import {gql, useApolloClient} from '@apollo/client';
import {TooltipProps} from '@mui/material';
import * as Colors from '@wandb/weave/common/css/color.styles';
import React, {useEffect, useState} from 'react';
import styled from 'styled-components';

import {DraggableHandle, StyledTooltip} from './DraggablePopups';
import {Link} from './PagePanelComponents/Home/Browse3/pages/common/Links';
import {RunState} from './RunState';
import {getTagContrastColor, Tag} from './Tag';
import {Tailwind} from './Tailwind';
import {Timestamp} from './Timestamp';

type RunLinkProps = {
  entityName: string;
  projectName: string;
  runName: string; // e.g. "qd58mkmj"
  placement?: TooltipProps['placement'];

  to?: string;
};

type TagColor = {
  id: string;
  name: string;
  colorIndex: number;
};

type RunData = {
  name: string;
  displayName: string;
  createdAt: string;
  notes: string;
  state: string;
  tagColors: TagColor[];
};

const FETCH_PROJECT_RUN_QUERY = gql`
  query FetchProjectRun(
    $entityName: String!
    $projectName: String!
    $runName: String!
  ) {
    project(entityName: $entityName, name: $projectName) {
      id
      internalId
      run(name: $runName) {
        id
        name
        displayName
        createdAt
        notes
        state
        tagColors {
          id
          name
          colorIndex
        }
      }
    }
  }
`;

type RunResult = 'load' | 'loading' | 'error' | RunData;

const RunContentHeader = styled.div`
  display: flex;
  align-items: center;
  padding: 2px 2px 2px 8px;
  background-color: ${Colors.MOON_100};
`;
RunContentHeader.displayName = 'S.RunContentHeader';

const RunDisplayName = styled.div`
  font-weight: 600;
  flex: 1 1 auto;
`;
RunDisplayName.displayName = 'S.RunDisplayName';

const RunContentBody = styled.div`
  padding: 4px;
  display: flex;
  align-items: flex-start;
  gap: 4px;
`;
RunContentBody.displayName = 'S.RunContentBody';

type RunContentProps = {run: RunData};

const RunContent = ({run}: RunContentProps) => {
  return (
    <Tailwind>
      <DraggableHandle>
        <RunContentHeader>
          <RunDisplayName>{run.displayName}</RunDisplayName>
        </RunContentHeader>
      </DraggableHandle>
      <RunContentBody>
        <div className="grid grid-cols-[auto_auto] gap-4">
          {run.notes && (
            <>
              <div className="text-right font-semibold">Notes</div>
              <div>{run.notes}</div>
            </>
          )}
          {run.tagColors.length > 0 && (
            <>
              <div className="text-right font-semibold">Tags</div>
              <div className="flex items-center gap-4">
                {run.tagColors.map(tag => (
                  <Tag
                    key={tag.id}
                    label={tag.name}
                    color={getTagContrastColor(tag.colorIndex)}
                  />
                ))}
              </div>
            </>
          )}
          <div className="text-right font-semibold">State</div>
          <div>
            <RunState value={run.state} />
          </div>
          <div className="text-right font-semibold">Start time</div>
          <div>
            <Timestamp value={run.createdAt} />
          </div>
        </div>
      </RunContentBody>
    </Tailwind>
  );
};

export const useProjectRun = (
  entityName: string,
  projectName: string,
  runName: string
) => {
  const apolloClient = useApolloClient();

  const [runData, setRunData] = useState<RunResult>('load');
  useEffect(() => {
    let mounted = true;
    setRunData('loading');
    apolloClient
      .query({
        query: FETCH_PROJECT_RUN_QUERY as any,
        variables: {
          entityName,
          projectName,
          runName,
        },
      })
      .then(runRes => {
        if (!mounted) {
          return;
        }
        const run = runRes.data.project.run;
        const {name, displayName, createdAt, notes, state, tagColors} = run;
        setRunData({
          name,
          displayName,
          createdAt,
          notes,
          state,
          tagColors,
        });
      })
      .catch(err => {
        console.error({err});
        if (!mounted) {
          return;
        }
        setRunData('error');
      });
    return () => {
      mounted = false;
    };
  }, [apolloClient, entityName, projectName, runName]);

  return runData;
};

export const RunLink = ({
  entityName,
  projectName,
  runName,
  placement,
  to,
}: RunLinkProps) => {
  const runData = useProjectRun(entityName, projectName, runName);
  if (runData === 'load' || runData === 'loading' || runData === 'error') {
    return null;
  }

  let content = <span className="font-semibold">{runData.displayName}</span>;
  if (to) {
    content = <Link to={to}>{content}</Link>;
  }
  const tooltipContent = <RunContent run={runData} />;

  return (
    <Tailwind>
      <StyledTooltip
        enterDelay={500}
        title={tooltipContent}
        placement={placement ?? 'right'}
        padding={0}>
        {content}
      </StyledTooltip>
    </Tailwind>
  );
};
