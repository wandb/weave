import {Box} from '@mui/material';
import {MOON_250} from '@wandb/weave/common/css/color.styles';
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Button} from '@wandb/weave/components/Button';
import {Loading} from '@wandb/weave/components/Loading';
import _ from 'lodash';
import React, {
  FC,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import ReactMarkdown from 'react-markdown';
import styled from 'styled-components';

import {WeaveflowPeekContext} from '../../context';
import {NotFoundPanel} from '../../NotFoundPanel';
import {
  LeaderboardColumnOrderType,
  LeaderboardGrid,
} from '../../views/Leaderboard/LeaderboardGrid';
import {useSavedLeaderboardData} from '../../views/Leaderboard/query/hookAdapters';
import {LeaderboardObjectVal} from '../../views/Leaderboard/types/leaderboardConfigType';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {
  useBaseObjectInstances,
  useCreateBuiltinObjectInstance,
} from '../wfReactInterface/objectClassQuery';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {LeaderboardConfigEditor} from './LeaderboardConfigEditor';

type LeaderboardPageProps = {
  entity: string;
  project: string;
  leaderboardName: string;
  openEditorOnMount?: boolean;
};

export const LeaderboardPage: React.FC<LeaderboardPageProps> = props => {
  const [name, setName] = useState(props.leaderboardName);
  const {isPeeking} = useContext(WeaveflowPeekContext);
  const {isEditor} = useIsEditor(props.entity);
  const [isEditing, setIsEditing] = useState(false);
  useEffect(() => {
    if (isEditor && props.openEditorOnMount) {
      setIsEditing(true);
    }
  }, [isEditor, props.openEditorOnMount]);
  return (
    <SimplePageLayout
      title={name}
      hideTabsIfSingle
      tabs={[
        {
          label: 'Leaderboard',
          content: (
            <LeaderboardPageContent
              {...props}
              setName={setName}
              isEditing={isEditing}
              setIsEditing={setIsEditing}
            />
          ),
        },
      ]}
      headerExtra={
        !isPeeking &&
        !isEditing &&
        isEditor && (
          <EditLeaderboardButton
            isEditing={isEditing}
            setIsEditing={setIsEditing}
          />
        )
      }
    />
  );
};

export const LeaderboardPageContent: React.FC<
  LeaderboardPageProps & {
    setName: (name: string) => void;
    isEditing: boolean;
    setIsEditing: (isEditing: boolean) => void;
  }
> = props => {
  const {entity, project} = props;
  const leaderboardInstances = useBaseObjectInstances('Leaderboard', {
    project_id: projectIdFromParts({entity, project}),
    filter: {object_ids: [props.leaderboardName], latest_only: true},
  });

  if (leaderboardInstances.loading) {
    return <Loading centered />;
  }

  if (
    leaderboardInstances.result == null ||
    leaderboardInstances.result.length !== 1
  ) {
    return (
      <NotFoundPanel
        title={`Leaderboard (${props.leaderboardName}) not found`}
      />
    );
  }

  const leaderboardVal = leaderboardInstances.result[0].val;

  if (leaderboardVal == null) {
    return (
      <NotFoundPanel
        title={`Leaderboard (${props.leaderboardName}) had invalid data`}
      />
    );
  }

  return (
    <LeaderboardPageContentInner
      {...props}
      leaderboardVal={leaderboardVal}
      setIsEditing={props.setIsEditing}
    />
  );
};

const useUpdateLeaderboard = (
  entity: string,
  project: string,
  objectId: string
) => {
  const createLeaderboard = useCreateBuiltinObjectInstance('Leaderboard');

  const updateLeaderboard = async (leaderboardVal: LeaderboardObjectVal) => {
    return await createLeaderboard({
      obj: {
        project_id: projectIdFromParts({entity, project}),
        object_id: objectId,
        val: leaderboardVal,
      },
    });
  };

  return updateLeaderboard;
};

export const LeaderboardPageContentInner: React.FC<
  LeaderboardPageProps & {
    setName: (name: string) => void;
    isEditing: boolean;
    setIsEditing: (isEditing: boolean) => void;
  } & {
    leaderboardVal: LeaderboardObjectVal;
  }
> = props => {
  const updateLeaderboard = useUpdateLeaderboard(
    props.entity,
    props.project,
    props.leaderboardName
  );
  const [leaderboardVal, setLeaderboardVal] = useState(props.leaderboardVal);
  const [workingLeaderboardValCopy, setWorkingLeaderboardValCopy] =
    useState(leaderboardVal);
  useEffect(() => {
    props.setName(workingLeaderboardValCopy.name ?? '');
  }, [props, workingLeaderboardValCopy.name]);
  const {loading, data, evalData} = useSavedLeaderboardData(
    props.entity,
    props.project,
    workingLeaderboardValCopy.columns
  );
  const [saving, setSaving] = useState(false);
  const discardChanges = useCallback(() => {
    setWorkingLeaderboardValCopy(leaderboardVal);
    props.setIsEditing(false);
  }, [leaderboardVal, props]);
  const commitChanges = useCallback(() => {
    const mounted = true;
    setSaving(true);
    updateLeaderboard(workingLeaderboardValCopy)
      .then(() => {
        if (mounted) {
          props.setIsEditing(false);
          setLeaderboardVal(workingLeaderboardValCopy);
          setWorkingLeaderboardValCopy(workingLeaderboardValCopy);
          setSaving(false);
        }
      })
      .catch(e => {
        console.error(e);
        if (mounted) {
          setWorkingLeaderboardValCopy(leaderboardVal);
          setSaving(false);
        }
      });
  }, [leaderboardVal, props, updateLeaderboard, workingLeaderboardValCopy]);
  const isDirty = useMemo(() => {
    return !_.isEqual(leaderboardVal, workingLeaderboardValCopy);
  }, [leaderboardVal, workingLeaderboardValCopy]);
  const columnOrder = useMemo(() => {
    return workingLeaderboardValCopy.columns
      .map(col => {
        const datasetGroup = evalData[col.evaluation_object_ref]?.datasetGroup;
        const scorerGroup =
          evalData[col.evaluation_object_ref]?.scorers[col.scorer_name];
        const metricGroup = col.summary_metric_path;

        if (datasetGroup && scorerGroup && metricGroup) {
          return {
            datasetGroup,
            scorerGroup,
            metricGroup,
            minimize: col.should_minimize ?? false,
          };
        }
        return null;
      })
      .filter(c => c != null) as LeaderboardColumnOrderType;
  }, [workingLeaderboardValCopy, evalData]);

  return (
    <Box display="flex" flexDirection="row" height="100%" flexGrow={1}>
      <Box
        flex={1}
        display="flex"
        flexDirection="column"
        height="100%"
        minWidth="50%">
        {workingLeaderboardValCopy.description && (
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
            <StyledReactMarkdown>
              {workingLeaderboardValCopy.description}
            </StyledReactMarkdown>
          </Box>
        )}
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
            columnOrder={columnOrder}
          />
        </Box>
      </Box>
      {props.isEditing && (
        <Box
          flex={1}
          display="flex"
          flexDirection="column"
          height="100%"
          minWidth="50%"
          sx={{
            borderLeft: `1px solid ${MOON_250}`,
          }}>
          <LeaderboardConfigEditor
            entity={props.entity}
            project={props.project}
            saving={saving}
            isDirty={isDirty}
            leaderboardVal={workingLeaderboardValCopy}
            setWorkingCopy={setWorkingLeaderboardValCopy}
            discardChanges={discardChanges}
            commitChanges={commitChanges}
          />
        </Box>
      )}
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

const EditLeaderboardButton: FC<{
  isEditing: boolean;
  setIsEditing: (isEditing: boolean) => void;
}> = ({isEditing, setIsEditing}) => {
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
        onClick={() => setIsEditing(!isEditing)}
        icon={isEditing ? 'close' : 'pencil-edit'}>
        {isEditing ? 'Discard Changes' : 'Edit'}
      </Button>
    </Box>
  );
};

export const useIsEditor = (entity: string) => {
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();
  return useMemo(() => {
    if (loadingUserInfo) {
      return {
        loading: true,
        isEditor: false,
      };
    }
    const viewer = userInfo ? userInfo.id : null;

    return {
      loading: false,
      isEditor: viewer && userInfo?.teams.includes(entity),
    };
  }, [entity, loadingUserInfo, userInfo]);
};

const StyledReactMarkdown = styled(ReactMarkdown)`
  > *:first-child {
    margin-top: 0;
  }
  h1 {
    font-weight: 600;
    font-size: 1.2rem;
  }
  h2 {
    font-weight: 600;
    font-size: 1.15rem;
  }
  h3 {
    font-weight: 600;
    font-size: 1.1rem;
  }
  h4 {
    font-weight: 600;
    font-size: 1.05rem;
  }
  h5 {
    font-weight: 600;
    font-size: 1rem;
  }
  h6 {
    font-weight: 600;
    font-size: 1rem;
  }
`;
