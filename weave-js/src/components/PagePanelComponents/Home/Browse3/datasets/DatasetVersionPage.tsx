import {Box, Tooltip} from '@mui/material';
import {UserLink} from '@wandb/weave/components/UserLink';
import {maybePluralize} from '@wandb/weave/core/util/string';
import {parseRefMaybe} from '@wandb/weave/react';
import React, {useCallback, useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {useDatasetStorageSizeCalculation} from '../../../../../common/hooks/useStorageSizeCalculation';
import {Button} from '../../../../Button';
import {Icon} from '../../../../Icon';
import {LoadingDots} from '../../../../LoadingDots';
import {Tailwind} from '../../../../Tailwind';
import {Timestamp} from '../../../../Timestamp';
import {useWeaveflowCurrentRouteContext} from '../context';
import {WeaveCHTableSourceRefContext} from '../pages/CallPage/DataTableView';
import {ObjectVersionsLink, objectVersionText} from '../pages/common/Links';
import {CenteredAnimatedLoader} from '../pages/common/Loader';
import {
  ScrollableTabContent,
  SimplePageLayoutWithHeader,
} from '../pages/common/SimplePageLayout';
import {StorageSizeSection} from '../pages/common/StorageSizeSection';
import {DeleteObjectButtonWithModal} from '../pages/ObjectsPage/ObjectDeleteButtons';
import {TabUseDataset} from '../pages/ObjectsPage/Tabs/TabUseDataset';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {objectVersionKeyToRefUri} from '../pages/wfReactInterface/utilities';
import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {CustomWeaveTypeProjectContext} from '../typeViews/CustomWeaveTypeDispatcher';
import {useDatasetEditContext} from './DatasetEditorContext';
import {updateExistingDataset} from './datasetOperations';
import {EditableDatasetView} from './EditableDatasetView';

const TOOLTIP_PROPS = {
  slotProps: {
    tooltip: {
      sx: {
        fontFamily: 'Source Sans Pro',
        fontSize: '14px',
      },
    },
  },
} as const;

export const DatasetVersionPage: React.FC<{
  objectVersion: ObjectVersionSchema;
  showDeleteButton?: boolean;
}> = ({objectVersion, showDeleteButton}) => {
  const {
    editedRows,
    deletedRows,
    addedRows,
    resetEditState,
    convertEditsToTableUpdateSpec,
  } = useDatasetEditContext();
  const router = useWeaveflowCurrentRouteContext();
  const {
    useRootObjectVersions,
    useRefsData,
    useTableUpdate,
    useObjCreate,
    useTableQueryStats,
  } = useWFHooks();

  const [isEditing, setIsEditing] = useState(false);

  const entityName = objectVersion.entity;
  const projectName = objectVersion.project;
  const objectName = objectVersion.objectId;
  const objectVersionIndex = objectVersion.versionIndex;
  const projectId = `${entityName}/${projectName}`;
  const {createdAtMs} = objectVersion;

  const objectVersions = useRootObjectVersions({
    entity: entityName,
    project: projectName,
    filter: {objectIds: [objectName]},
    includeStorageSize: true,
  });
  const objectVersionCount = (objectVersions.result ?? []).length;
  const refUri = objectVersionKeyToRefUri(objectVersion);

  const data = useRefsData({refUris: [refUri]});

  const handleEditClick = useCallback(() => setIsEditing(true), []);
  const handleCancelClick = useCallback(() => {
    resetEditState();
    setIsEditing(false);
  }, [resetEditState]);

  const tableUpdate = useTableUpdate();
  const objCreate = useObjCreate();

  const history = useHistory();

  const handlePublish = useCallback(async () => {
    setIsEditing(false);

    const {url} = await updateExistingDataset({
      projectId,
      entity: entityName,
      project: projectName,
      selectedDataset: objectVersion,
      datasetObject: objectVersion.val,
      updateSpecs: convertEditsToTableUpdateSpec(),
      tableUpdate,
      objCreate,
      router,
    });

    history.push(url);
    resetEditState();
  }, [
    objectVersion,
    resetEditState,
    history,
    router,
    convertEditsToTableUpdateSpec,
    projectId,
    objCreate,
    tableUpdate,
    entityName,
    projectName,
  ]);

  const tableDigests = useMemo(() => {
    if (objectVersions.loading || objectVersions.result == null) {
      return null;
    }
    return Array.from(
      new Set(
        objectVersions.result.map(v => {
          const ref = parseRefMaybe(v.val.rows);
          return ref?.artifactVersion;
        })
      )
    ).filter(Boolean) as string[];
  }, [objectVersions]);

  const digests = useMemo(() => {
    return tableDigests ?? [];
  }, [tableDigests]);
  const tableStats = useTableQueryStats({
    entity: entityName,
    project: projectName,
    digests,
    skip: digests == null,
    includeStorageSize: true,
  });

  const {
    currentVersionSizeBytes,
    allVersionsSizeBytes,
    shouldShowAllVersions,
    isLoading,
  } = useDatasetStorageSizeCalculation(
    objectVersions,
    objectVersionIndex,
    tableStats
  );

  const renderEditingControls = () => {
    const editCountStr = String(Array.from(editedRows.keys()).length);
    const addedCountStr = String(addedRows.size);
    const deletedCountStr = String(deletedRows.length);
    return (
      <div className="flex gap-8">
        <div className="absolute right-[28px] top-[68px] flex gap-8 font-mono text-xs">
          <Tooltip
            title={`${maybePluralize(Number(addedCountStr), 'row')} added`}
            {...TOOLTIP_PROPS}>
            <div className="flex items-center gap-1 text-xs font-semibold text-moon-500">
              <Icon name="add-new" width={12} height={12} />
              <span>{addedCountStr}</span>
            </div>
          </Tooltip>
          <Tooltip
            title={`${maybePluralize(Number(deletedCountStr), 'row')} deleted`}
            {...TOOLTIP_PROPS}>
            <div className="flex items-center gap-1 text-xs font-semibold text-moon-500">
              <Icon name="remove" width={12} height={12} />
              <span>{deletedCountStr}</span>
            </div>
          </Tooltip>
          <Tooltip
            title={`${maybePluralize(Number(editCountStr), 'row')} edited`}
            {...TOOLTIP_PROPS}>
            <div className="flex items-center gap-1 text-xs font-semibold text-moon-500">
              <Icon name="pencil-edit" width={12} height={12} />
              <span>{editCountStr}</span>
            </div>
          </Tooltip>
        </div>
        <Button
          title="Cancel"
          tooltip="Cancel"
          variant="secondary"
          size="medium"
          onClick={handleCancelClick}>
          Cancel
        </Button>
        <Button
          title="Publish"
          tooltip="Publish"
          size="medium"
          variant="primary"
          icon="checkmark"
          onClick={handlePublish}
          disabled={
            editCountStr === '0' &&
            deletedCountStr === '0' &&
            addedCountStr === '0'
          }>
          Publish
        </Button>
      </div>
    );
  };

  return (
    <SimplePageLayoutWithHeader
      title={
        <Tailwind>
          <div className="flex items-center gap-8">
            <div className="flex h-22 w-22 items-center justify-center rounded-full bg-moon-300/[0.48] text-moon-600">
              <Icon width={14} height={14} name="table" />
            </div>
            <span data-testid="dataset-version-page-name">
              {objectVersionText(objectName, objectVersionIndex)}
            </span>
          </div>
        </Tailwind>
      }
      headerContent={
        <Tailwind>
          <div className="flex justify-between">
            <div className="grid auto-cols-max grid-flow-col gap-[16px] overflow-x-auto text-[14px]">
              <div className="block">
                <p className="text-moon-500">Name</p>
                <ObjectVersionsLink
                  entity={entityName}
                  project={projectName}
                  filter={{objectName}}
                  versionCount={objectVersionCount}
                  neverPeek
                  variant="secondary">
                  <div className="group flex items-center font-semibold">
                    <span>{objectName}</span>
                    {objectVersions.loading ? (
                      <LoadingDots />
                    ) : (
                      <span className="ml-[4px]">
                        ({maybePluralize(objectVersionCount, 'version')})
                      </span>
                    )}
                    <Icon
                      name="forward-next"
                      width={16}
                      height={16}
                      className="ml-[2px] opacity-0 group-hover:opacity-100"
                    />
                  </div>
                </ObjectVersionsLink>
              </div>
              <div className="block">
                <p className="text-moon-500">Version</p>
                <p>{objectVersionIndex}</p>
              </div>
              <div className="block">
                <p className="text-moon-500">Created</p>
                <p>
                  <Timestamp value={createdAtMs / 1000} format="relative" />
                </p>
              </div>
              {objectVersion.userId && (
                <div className="block">
                  <p className="text-moon-500">Created by</p>
                  <UserLink userId={objectVersion.userId} includeName />
                </div>
              )}
              <StorageSizeSection
                isLoading={isLoading}
                shouldShowAllVersions={shouldShowAllVersions}
                currentVersionBytes={currentVersionSizeBytes}
                allVersionsSizeBytes={allVersionsSizeBytes}
              />
            </div>

            <div className="ml-auto flex-shrink-0">
              {isEditing ? (
                renderEditingControls()
              ) : (
                <Button
                  title="Edit dataset"
                  tooltip="Edit dataset"
                  variant="ghost"
                  size="medium"
                  icon="pencil-edit"
                  onClick={handleEditClick}
                />
              )}
              {showDeleteButton && !isEditing && (
                <DeleteObjectButtonWithModal objVersionSchema={objectVersion} />
              )}
            </div>
          </div>
        </Tailwind>
      }
      tabs={
        !isEditing
          ? [
              {
                label: 'Rows',
                content: (
                  <ScrollableTabContent sx={{p: 0}}>
                    <Box sx={{flex: '0 0 auto', height: '100%'}}>
                      {data.loading ? (
                        <CenteredAnimatedLoader />
                      ) : (
                        <WeaveCHTableSourceRefContext.Provider value={refUri}>
                          <CustomWeaveTypeProjectContext.Provider
                            value={{entity: entityName, project: projectName}}>
                            <EditableDatasetView
                              isEditing={isEditing}
                              datasetObject={objectVersion.val}
                            />
                          </CustomWeaveTypeProjectContext.Provider>
                        </WeaveCHTableSourceRefContext.Provider>
                      )}
                    </Box>
                  </ScrollableTabContent>
                ),
              },
              {
                label: 'Use',
                content: (
                  <ScrollableTabContent>
                    <Tailwind>
                      <TabUseDataset
                        name={objectName}
                        uri={refUri}
                        versionIndex={objectVersionIndex}
                      />
                    </Tailwind>
                  </ScrollableTabContent>
                ),
              },
            ]
          : [
              {
                label: 'Editing',
                content: (
                  <ScrollableTabContent sx={{p: 0}}>
                    <Box sx={{flex: '0 0 auto', height: '100%'}}>
                      {data.loading ? (
                        <CenteredAnimatedLoader />
                      ) : (
                        <WeaveCHTableSourceRefContext.Provider value={refUri}>
                          <CustomWeaveTypeProjectContext.Provider
                            value={{entity: entityName, project: projectName}}>
                            <EditableDatasetView
                              isEditing={isEditing}
                              datasetObject={objectVersion.val}
                            />
                          </CustomWeaveTypeProjectContext.Provider>
                        </WeaveCHTableSourceRefContext.Provider>
                      )}
                    </Box>
                  </ScrollableTabContent>
                ),
              },
            ]
      }
    />
  );
};
