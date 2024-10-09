import {Alert, Box, Typography} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
import React, {useCallback, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../../context';
import {EditableMarkdown} from './EditableMarkdown';
import {useLeaderboardData} from './hooks';
import {LeaderboardConfigType} from './LeaderboardConfigType';
import {LeaderboardGrid} from './LeaderboardGrid';
import {LeaderboardConfig} from './LeaderboardPageConfig';
import {
  persistLeaderboardConfig,
  useCurrentLeaderboardConfig,
} from './useCurrentLeaderboardConfig';

const USE_COMPARE_EVALUATIONS_PAGE = false;

type LeaderboardPageProps = {
  entity: string;
  project: string;
};

export const LeaderboardPage: React.FC<LeaderboardPageProps> = props => {
  return (
    <LeaderboardPageContent entity={props.entity} project={props.project} />
  );
};

const DEFAULT_DESCRIPTION = `# Leaderboard`;

const usePersistedLeaderboardConfig = () => {
  const initialConfig = useCurrentLeaderboardConfig();
  const [config, setConfigLocal] =
    useState<LeaderboardConfigType>(initialConfig);

  const persistConfig = useCallback(() => {
    persistLeaderboardConfig(config);
  }, [config]);

  const cancelChanges = useCallback(() => {
    setConfigLocal(initialConfig);
  }, [initialConfig]);

  return {config, setConfigLocal, persistConfig, cancelChanges};
};

export const LeaderboardPageContent: React.FC<LeaderboardPageProps> = props => {
  const {entity, project} = props;

  const {peekingRouter} = useWeaveflowRouteContext();
  const history = useHistory();

  const [showConfig, setShowConfig] = useState(false);

  const {
    config: currentConfig,
    setConfigLocal,
    persistConfig,
    cancelChanges,
  } = usePersistedLeaderboardConfig();
  const description = currentConfig.config.description;
  const setDescription = useCallback(
    (newDescription: string) => {
      setConfigLocal(newConfig => ({
        ...newConfig,
        config: {...newConfig.config, description: newDescription},
      }));
      persistConfig();
    },
    [setConfigLocal, persistConfig]
  );

  const {loading, data} = useLeaderboardData(entity, project, currentConfig);

  const handleCellClick = (
    modelName: string,
    metricName: string,
    score: number
  ) => {
    const sourceCallId = data.scores?.[modelName]?.[metricName]?.sourceCallId;
    if (sourceCallId) {
      let to: string;
      if (USE_COMPARE_EVALUATIONS_PAGE) {
        to = peekingRouter.compareEvaluationsUri(entity, project, [
          sourceCallId,
        ]);
      } else {
        to = peekingRouter.callUIUrl(entity, project, '', sourceCallId, null);
      }
      history.push(to);
    }
  };

  const [showingAlert, setShowingAlert] = useState(true);

  return (
    <Box display="flex" flexDirection="column" height="100%">
      {showingAlert && <UnlistedAlert onClose={() => setShowingAlert(false)} />}
      <div
        style={{
          position: 'absolute',
          top: 20 + (showingAlert ? 52 : 0),
          right: 24,
        }}>
        <ToggleLeaderboardConfig
          isOpen={showConfig}
          onClick={() => setShowConfig(c => !c)}
        />
      </div>
      <Box flexShrink={0} maxHeight="35%" overflow="auto">
        <EditableMarkdown
          value={description}
          onChange={setDescription}
          placeholder={DEFAULT_DESCRIPTION}
        />
      </Box>
      <Box
        flexGrow={1}
        display="flex"
        flexDirection="row"
        overflow="hidden"
        minHeight="65%">
        <LeaderboardGrid
          loading={loading}
          data={data}
          onCellClick={handleCellClick}
        />
        {showConfig && (
          <LeaderboardConfig
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
        )}
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
        size="medium"
        onClick={onClick}
        tooltip={isOpen ? 'Discard Changes' : 'Configure Leaderboard'}
        icon={isOpen ? 'close' : 'settings'}
      />
    </Box>
  );
};

const UnlistedAlert: React.FC<{onClose: () => void}> = ({onClose}) => {
  return (
    <Alert severity="info" onClose={onClose}>
      <Typography variant="body1">
        You have found an internal, unlisted beta page! Please expect bugs and
        incomplete features. Permilinks are not yet supported.
      </Typography>
    </Alert>
  );
};
