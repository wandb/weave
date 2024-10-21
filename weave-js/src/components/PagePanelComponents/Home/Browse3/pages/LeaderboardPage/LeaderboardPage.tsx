import {Box} from '@mui/material';
import {MOON_250} from '@wandb/weave/common/css/color.styles';
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Button} from '@wandb/weave/components/Button';
import {ErrorPanel} from '@wandb/weave/components/ErrorPanel';
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

import {WeaveflowPeekContext} from '../../context';
import {NotFoundPanel} from '../../NotFoundPanel';
import {LeaderboardGrid} from '../../views/Leaderboard/LeaderboardGrid';
import {usePythonLeaderboardData} from '../../views/Leaderboard/query/hookAdapters';
import {PythonLeaderboardObjectVal} from '../../views/Leaderboard/types/leaderboardConfigType';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {useWFHooks} from '../wfReactInterface/context';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {StyledReactMarkdown} from './EditableMarkdown';
import {LeaderboardConfigEditor} from './LeaderboardConfigEditor';

type LeaderboardPageProps = {
  entity: string;
  project: string;
  leaderboardName: string;
};

export const LeaderboardPage: React.FC<LeaderboardPageProps> = props => {
  const [name, setName] = useState(props.leaderboardName);
  const {isPeeking} = useContext(WeaveflowPeekContext);
  const [isEditing, setIsEditing] = useState(false);
  const {isEditor} = useIsEditor(props.entity);
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
  const getTsClient = useGetTraceServerClientContext();
  const client = getTsClient();

  const updateLeaderboard = async (
    leaderboardVal: PythonLeaderboardObjectVal
  ) => {
    return await client.objCreate({
      obj: {
        project_id: projectIdFromParts({entity, project}),
        object_id: objectId,
        val: {
          _type: 'Leaderboard',
          _class_name: 'Leaderboard',
          _bases: ['Object', 'BaseModel'],
          ...leaderboardVal,
        },
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
    leaderboardVal: PythonLeaderboardObjectVal;
  }
> = props => {
  const updateLeaderboard = useUpdateLeaderboard(
    props.entity,
    props.project,
    props.leaderboardName
  );
  const [workingLeaderboardValCopy, setWorkingLeaderboardValCopy] = useState(
    props.leaderboardVal
  );
  useEffect(() => {
    props.setName(workingLeaderboardValCopy.name);
  }, [props, workingLeaderboardValCopy.name]);
  const {loading, data} = usePythonLeaderboardData(
    props.entity,
    props.project,
    workingLeaderboardValCopy
  );
  const [saving, setSaving] = useState(false);
  const discardChanges = useCallback(() => {
    setWorkingLeaderboardValCopy(props.leaderboardVal);
    props.setIsEditing(false);
  }, [props]);
  const commitChanges = useCallback(() => {
    const mounted = true;
    setSaving(true);
    updateLeaderboard(workingLeaderboardValCopy)
      .then(() => {
        if (mounted) {
          props.setIsEditing(false);
          setSaving(false);
        }
      })
      .catch(e => {
        console.error(e);
        if (mounted) {
          setWorkingLeaderboardValCopy(props.leaderboardVal);
          setSaving(false);
        }
      });
  }, [props, updateLeaderboard, workingLeaderboardValCopy]);
  const isDirty = useMemo(() => {
    return !_.isEqual(props.leaderboardVal, workingLeaderboardValCopy);
  }, [props.leaderboardVal, workingLeaderboardValCopy]);

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

const useIsEditor = (entity: string) => {
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
