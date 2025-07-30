/**
 * This page is specifically for prompts. It shows a list of prompt objects and their versions.
 * It is inspired by ObjectVersionsPage but tailored specifically for the prompt use case.
 */
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {Loading} from '../../../../../Loading';
import {useEntityProject, useWeaveflowCurrentRouteContext} from '../../context';
import {CreatePromptDrawer} from '../../prompts/CreatePromptDrawer';
import {usePromptSaving} from '../../prompts/usePromptSaving';
import {EMPTY_PROPS_PROMPTS} from '../common/EmptyContent';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {
  DeleteObjectsButtonWithModal,
  DeleteObjectVersionsButtonWithModal,
} from '../ObjectsPage/ObjectDeleteButtons';
import {WFHighLevelObjectVersionFilter} from '../ObjectsPage/objectsPageTypes';
import {FilterableObjectVersionsTable} from '../ObjectsPage/ObjectVersionsTable';
import {useControllableState} from '../util';

export type PromptFilter = WFHighLevelObjectVersionFilter;

const PROMPT_TYPE = 'Prompt' as const;

export const PromptsPage: React.FC<{
  initialFilter?: PromptFilter;
  onFilterUpdate?: (filter: PromptFilter) => void;
}> = props => {
  const {entity, project} = useEntityProject()
  const history = useHistory();
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();
  const router = useWeaveflowCurrentRouteContext();

  const [isCreateDrawerOpen, setIsCreateDrawerOpen] = useState(false);

  const {isCreatingPrompt, handleSavePrompt} = usePromptSaving({
    entity,
    project,
    onSaveComplete: () => setIsCreateDrawerOpen(false),
  });

  const baseFilter = useMemo(() => {
    return {
      ...props.initialFilter,
      baseObjectClass: PROMPT_TYPE,
    };
  }, [props.initialFilter]);

  const [filter, setFilter] =
    useControllableState<WFHighLevelObjectVersionFilter>(
      baseFilter ?? {baseObjectClass: PROMPT_TYPE},
      props.onFilterUpdate
    );

  const [selectedVersions, setSelectedVersions] = useState<string[]>([]);

  const onCompare = () => {
    history.push(router.compareObjectsUri(entity, project, selectedVersions));
  };

  const title = useMemo(() => {
    if (filter.objectName) {
      return `Versions of ${filter.objectName}`;
    }
    return 'Prompts';
  }, [filter.objectName]);

  const handleCreatePrompt = () => {
    setIsCreateDrawerOpen(true);
  };

  const handleCloseDrawer = () => {
    setIsCreateDrawerOpen(false);
  };

  if (loadingUserInfo) {
    return <Loading />;
  }

  const filteredOnObject = filter.objectName != null;
  const hasComparison = filteredOnObject;
  const viewer = userInfo ? userInfo.id : null;
  const isReadonly = !viewer || !userInfo?.teams.includes(entity);
  const isAdmin = userInfo?.admin;

  // TODO: We should probably not show the delete button in the header when
  //       there are no prompts in the project.
  const showDeleteButton = !isReadonly && isAdmin;

  return (
    <>
      <SimplePageLayout
        title={title}
        hideTabsIfSingle
        headerExtra={
          <PromptsPageHeaderExtra
            objectName={filter.objectName ?? null}
            selectedVersions={selectedVersions}
            setSelectedVersions={setSelectedVersions}
            showDeleteButton={showDeleteButton}
            showCompareButton={hasComparison}
            onCompare={onCompare}
            onCreatePrompt={handleCreatePrompt}
            isReadonly={isReadonly}
          />
        }
        tabs={[
          {
            label: '',
            content: (
              <FilterableObjectVersionsTable
                entity={entity}
                project={project}
                initialFilter={filter}
                onFilterUpdate={setFilter}
                selectedVersions={selectedVersions}
                setSelectedVersions={setSelectedVersions}
                propsEmpty={EMPTY_PROPS_PROMPTS}
              />
            ),
          },
        ]}
      />

      <CreatePromptDrawer
        open={isCreateDrawerOpen}
        onClose={handleCloseDrawer}
        onSavePrompt={handleSavePrompt}
        isCreating={isCreatingPrompt}
      />
    </>
  );
};

const PromptsPageHeaderExtra: React.FC<{
  objectName: string | null;
  selectedVersions: string[];
  setSelectedVersions: (selected: string[]) => void;
  showDeleteButton?: boolean;
  showCompareButton?: boolean;
  onCompare: () => void;
  onCreatePrompt: () => void;
  isReadonly: boolean;
}> = ({
  objectName,
  selectedVersions,
  setSelectedVersions,
  showDeleteButton,
  showCompareButton,
  onCompare,
  onCreatePrompt,
  isReadonly,
}) => {
  const {entity, project} = useEntityProject();
  const compareButton = showCompareButton ? (
    <Button disabled={selectedVersions.length < 2} onClick={onCompare}>
      Compare
    </Button>
  ) : undefined;

  const deleteButton = showDeleteButton ? (
    objectName ? (
      <DeleteObjectVersionsButtonWithModal
        entity={entity}
        project={project}
        objectName={objectName}
        objectVersions={selectedVersions}
        disabled={selectedVersions.length === 0}
        onSuccess={() => setSelectedVersions([])}
        tooltip="Delete selected prompt versions"
      />
    ) : (
      <DeleteObjectsButtonWithModal
        entity={entity}
        project={project}
        objectIds={selectedVersions.map(v => v.split(':')[0])}
        disabled={selectedVersions.length === 0}
        onSuccess={() => setSelectedVersions([])}
        tooltip="Delete all versions of selected prompts"
      />
    )
  ) : undefined;

  return (
    <Tailwind>
      <div className="mr-16 flex gap-8">
        {!isReadonly && (
          <Button
            icon="add-new"
            variant="ghost"
            onClick={onCreatePrompt}
            tooltip="Create a new prompt">
            New prompt
          </Button>
        )}
        {compareButton}
        {deleteButton}
      </div>
    </Tailwind>
  );
};
