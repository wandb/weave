import {Box} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
import {ErrorPanel} from '@wandb/weave/components/ErrorPanel';
import {Loading} from '@wandb/weave/components/Loading';
import React, {useCallback, useEffect, useMemo, useState} from 'react';

import {parseRefMaybe} from '../../../Browse2/SmallRef';
import {NotFoundPanel} from '../../NotFoundPanel';
import {LeaderboardGrid} from '../../views/Leaderboard/LeaderboardGrid';
import {useLeaderboardData} from '../../views/Leaderboard/query/hookAdapters';
import {
  FilterAndGroupSourceEvaluationSpec,
  FilterAndGroupSpec,
  LeaderboardConfigType,
} from '../../views/Leaderboard/types/leaderboardConfigType';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {useWFHooks} from '../wfReactInterface/context';
import {EditableMarkdown, StyledReactMarkdown} from './EditableMarkdown';
import {LeaderboardConfigEditor} from './LeaderboardConfigEditor';

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

const DEFAULT_DESCRIPTION = `# Leaderboard`;

const usePersistedLeaderboardConfig = () => {
  const [configPersisted, setConfigPersisted] = useState<LeaderboardConfigType>(
    {
      version: 1,
      config: {description: '', dataSelectionSpec: {}},
    }
  );

  const [config, setConfigLocal] =
    useState<LeaderboardConfigType>(configPersisted);

  const persistConfig = useCallback(() => {
    setConfigPersisted(config);
    // persistLeaderboardConfig(config);
  }, [config]);

  const cancelChanges = useCallback(() => {
    setConfigLocal(configPersisted);
  }, [configPersisted]);

  return {config, setConfigLocal, persistConfig, cancelChanges};
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
    leaderboardVal: LeaderboardVal;
  }
> = props => {
  useEffect(() => {
    props.setName(props.leaderboardVal.name);
  }, [props]);

  // const [showConfig, setShowConfig] = useState(false);

  // const {
  //   config: currentConfig,
  //   setConfigLocal,
  //   persistConfig,
  //   cancelChanges,
  // } = usePersistedLeaderboardConfig();
  // const setDescription = useCallback(
  //   (newDescription: string) => {
  //     setConfigLocal(newConfig => ({
  //       ...newConfig,
  //       config: {...newConfig.config, description: newDescription},
  //     }));
  //     persistConfig();
  //   },
  //   [setConfigLocal, persistConfig]
  // );

  const spec = useMemo(() => {
    return convertLeaderboardValToFilterAndGroupSpec(props.leaderboardVal);
  }, [props.leaderboardVal]);

  const description = props.leaderboardVal.description;
  const {loading, data} = useLeaderboardData(props.entity, props.project, spec);

  return (
    <Box display="flex" flexDirection="row" height="100%" flexGrow={1}>
      <Box
        flex={1}
        display="flex"
        flexDirection="column"
        height="100%"
        minWidth="50%">
        <Box
          flex={1}
          display="flex"
          flexDirection="row"
          maxHeight="35%"
          width="100%"
          sx={{
            alignItems: 'flex-start',
            padding: '12px 16px',
            gap: '12px',
          }}>
          <Box
            flexShrink={0}
            flexGrow={1}
            sx={{
              overflow: 'auto',
              height: '100%',
              display: 'flex',
              alignItems: 'flex-start',
            }}>
            {description && (
              <StyledReactMarkdown>{description}</StyledReactMarkdown>
            )}
            {/* <EditableMarkdown
              value={props.leaderboardName + '\n' + description}
              onChange={setDescription}
              placeholder={DEFAULT_DESCRIPTION}
            /> */}
          </Box>
          {/* <div
            style={{
              display: showConfig ? 'none' : 'block',
              // paddingRight: '12px',
              // paddingTop: '12px',
            }}>
            <ToggleLeaderboardConfig
              isOpen={showConfig}
              onClick={() => setShowConfig(c => !c)}
            />
          </div> */}
        </Box>
        <Box flexGrow={1} display="flex" flexDirection="row" overflow="hidden">
          <LeaderboardGrid
            entity={props.entity}
            project={props.project}
            loading={loading}
            data={data}
          />
        </Box>
      </Box>
      {/* {showConfig && (
        <Box flex={1} width="35%" height="100%" overflow="hidden">
          <LeaderboardConfigEditor
            entity={entity}
            project={project}
            config={currentConfig}
            onCancel={() => {
              cancelChanges();
              setShowConfig(false);
            }}
            onPersist={() => {
              persistConfig();
              setShowConfig(false);
            }}
            setConfig={setConfigLocal}
          />
        </Box>
      )} */}
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

type LeaderboardVal = {
  name: string;
  description: string;
  columns: Array<{
    evaluation_object_ref: string;
    scorer_name: string;
    should_minimize?: boolean;
    summary_metric_path_parts: string[];
  }>;
};

const parseLeaderboardVal = (leaderboardVal: any): LeaderboardVal | null => {
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
    .filter(column => column != null) as LeaderboardVal['columns'];

  return {
    name,
    description,
    columns: finalColumns,
  };
};

/**
 * Note: this is a breidge between the python type and the js type.
 */
const convertLeaderboardValToFilterAndGroupSpec = (
  leaderboardVal: LeaderboardVal
): FilterAndGroupSpec => {
  const allEvaluations = new Set<string>();
  leaderboardVal.columns.forEach(column => {
    allEvaluations.add(column.evaluation_object_ref);
  });
  const sourceEvaluations = Array.from(allEvaluations)
    .map(evaluation => {
      const evalRef = parseRefMaybe(evaluation);
      if (evalRef == null) {
        return null;
      }
      return {
        name: evalRef.artifactName,
        version: evalRef.artifactVersion,
      };
    })
    .filter(
      evaluation => evaluation != null
    ) as FilterAndGroupSourceEvaluationSpec[];

  const scorers = leaderboardVal.columns.map(column => {
    return {
      name: column.scorer_name,
      version: '*',
      metrics: [
        {
          path: column.summary_metric_path_parts.join('.'),
          shouldMinimize: column.should_minimize,
        },
      ],
    };
  });
  return {
    sourceEvaluations,
    datasets: [
      {
        name: '*',
        version: '*',
        scorers,
      },
    ],
  };
};
