import {Box} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
import {ErrorPanel} from '@wandb/weave/components/ErrorPanel';
import {Loading} from '@wandb/weave/components/Loading';
import React, {useEffect, useState} from 'react';

import {NotFoundPanel} from '../../NotFoundPanel';
import {LeaderboardGrid} from '../../views/Leaderboard/LeaderboardGrid';
import {usePythonLeaderboardData} from '../../views/Leaderboard/query/hookAdapters';
import {PythonLeaderboardObjectVal} from '../../views/Leaderboard/types/leaderboardConfigType';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {useWFHooks} from '../wfReactInterface/context';
import {StyledReactMarkdown} from './EditableMarkdown';

type LeaderboardPageProps = {
  entity: string;
  project: string;
  leaderboardName: string;
};

export const LeaderboardPage: React.FC<LeaderboardPageProps> = props => {
  const [name, setName] = useState(props.leaderboardName);
  return (
    <SimplePageLayout
      title={name}
      hideTabsIfSingle
      tabs={[
        {
          label: 'Leaderboard',
          content: <LeaderboardPageContent {...props} setName={setName} />,
        },
      ]}
    />
  );
};

export const LeaderboardPageContent: React.FC<
  LeaderboardPageProps & {setName: (name: string) => void}
> = props => {
  const {useRootObjectVersions} = useWFHooks();
  const {entity, project} = props;
  const leaderboardObjectVersion = useRootObjectVersions(entity, project, {
    objectIds: [props.leaderboardName],
    baseObjectClasses: ['Leaderboard'],
    latestOnly: true,
  });

  if (leaderboardObjectVersion.loading) {
    return <Loading centered />;
  }

  if (leaderboardObjectVersion.error) {
    return <ErrorPanel />;
  }

  if (
    leaderboardObjectVersion.result == null ||
    leaderboardObjectVersion.result.length !== 1
  ) {
    return (
      <NotFoundPanel
        title={`Leaderboard (${props.leaderboardName}) not found`}
      />
    );
  }

  const leaderboardVal = parseLeaderboardVal(
    leaderboardObjectVersion.result[0].val
  );

  if (leaderboardVal == null) {
    return (
      <NotFoundPanel
        title={`Leaderboard (${props.leaderboardName}) had invalid data`}
      />
    );
  }

  return (
    <LeaderboardPageContentInner {...props} leaderboardVal={leaderboardVal} />
  );
};

export const LeaderboardPageContentInner: React.FC<
  LeaderboardPageProps & {setName: (name: string) => void} & {
    leaderboardVal: PythonLeaderboardObjectVal;
  }
> = props => {
  useEffect(() => {
    props.setName(props.leaderboardVal.name);
  }, [props]);

  const description = props.leaderboardVal.description;
  const {loading, data} = usePythonLeaderboardData(
    props.entity,
    props.project,
    props.leaderboardVal
  );

  return (
    <Box display="flex" flexDirection="row" height="100%" flexGrow={1}>
      <Box
        flex={1}
        display="flex"
        flexDirection="column"
        height="100%"
        minWidth="50%">
        <Box
          display="flex"
          flexDirection="row"
          maxHeight="35%"
          width="100%"
          sx={{
            flex: '1 1 auto',
            alignItems: 'flex-start',
            padding: '12px 16px',
            gap: '12px',
            overflowY: 'auto',
          }}>
          {description && (
            <StyledReactMarkdown>{description}</StyledReactMarkdown>
          )}
        </Box>
        <Box
          display="flex"
          flexDirection="row"
          overflow="hidden"
          sx={{
            flex: '1 1 auto',
          }}>
          <LeaderboardGrid
            entity={props.entity}
            project={props.project}
            loading={loading}
            data={data}
          />
        </Box>
      </Box>
    </Box>
  );
};

export const ToggleLeaderboardConfig: React.FC<{
  isOpen: boolean;
  onClick: () => void;
}> = ({isOpen, onClick}) => {
  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
      }}>
      <Button
        variant="ghost"
        size="small"
        onClick={onClick}
        tooltip={isOpen ? 'Discard Changes' : 'Configure Leaderboard'}
        icon={isOpen ? 'close' : 'settings'}
      />
    </Box>
  );
};

const parseLeaderboardVal = (
  leaderboardVal: any
): PythonLeaderboardObjectVal | null => {
  if (typeof leaderboardVal !== 'object' || leaderboardVal == null) {
    return null;
  }

  const name = leaderboardVal.name;
  if (typeof name !== 'string') {
    return null;
  }

  const description = leaderboardVal.description;
  if (typeof description !== 'string') {
    return null;
  }

  const columns = leaderboardVal.columns;
  if (!Array.isArray(columns)) {
    return null;
  }

  const finalColumns = columns
    .map(column => {
      const evaluationObjectRef = column.evaluation_object_ref;
      if (typeof evaluationObjectRef !== 'string') {
        return null;
      }

      const scorerName = column.scorer_name;
      if (typeof scorerName !== 'string') {
        return null;
      }

      const shouldMinimize = column.should_minimize;
      if (shouldMinimize != null && typeof shouldMinimize !== 'boolean') {
        return null;
      }

      const summaryMetricParts = column.summary_metric_path_parts;
      if (!Array.isArray(summaryMetricParts)) {
        return null;
      } else if (summaryMetricParts.some(part => typeof part !== 'string')) {
        return null;
      }

      return {
        evaluation_object_ref: evaluationObjectRef,
        scorer_name: scorerName,
        should_minimize: shouldMinimize,
        summary_metric_path_parts: summaryMetricParts,
      };
    })
    .filter(column => column != null) as PythonLeaderboardObjectVal['columns'];

  return {
    name,
    description,
    columns: finalColumns,
  };
};
