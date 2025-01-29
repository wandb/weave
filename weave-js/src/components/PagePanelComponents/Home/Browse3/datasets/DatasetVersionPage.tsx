import {Box, Tooltip} from '@mui/material';
import {UserLink} from '@wandb/weave/components/UserLink';
import {maybePluralize} from '@wandb/weave/core/util/string';
import React, {useCallback, useMemo, useState} from 'react';
import {Link, useHistory} from 'react-router-dom';
import {toast} from 'react-toastify';

import {Button} from '../../../../Button';
import {Icon} from '../../../../Icon';
import {LoadingDots} from '../../../../LoadingDots';
import {Pill} from '../../../../Tag/Pill';
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
import {DeleteObjectButtonWithModal} from '../pages/ObjectsPage/ObjectDeleteButtons';
import {TabUseDataset} from '../pages/ObjectsPage/Tabs/TabUseDataset';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {objectVersionKeyToRefUri} from '../pages/wfReactInterface/utilities';
import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {CustomWeaveTypeProjectContext} from '../typeViews/CustomWeaveTypeDispatcher';
import {useDatasetEditContext} from './DatasetEditorContext';
import {EditableDatasetView} from './EditableDatasetView';

const PUBLISHED_LINK_STYLES = {
  color: 'rgb(94, 234, 212)',
  textDecoration: 'none',
  fontFamily: 'Inconsolata',
  fontWeight: 600,
} as const;

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
  const {useRootObjectVersions, useRefsData, useTableUpdate, useObjCreate} =
    useWFHooks();

  const [isEditing, setIsEditing] = useState(false);

  const entityName = objectVersion.entity;
  const projectName = objectVersion.project;
  const objectName = objectVersion.objectId;
  const objectVersionIndex = objectVersion.versionIndex;
  const projectId = `${entityName}/${projectName}`;
  const {createdAtMs} = objectVersion;

  const objectVersions = useRootObjectVersions(
    entityName,
    projectName,
    {objectIds: [objectName]},
    undefined,
    true
  );
  const objectVersionCount = (objectVersions.result ?? []).length;
  const refUri = objectVersionKeyToRefUri(objectVersion);

  const data = useRefsData([refUri]);
  const viewerData = useMemo(() => {
    if (data.loading) {
      return {};
    }
    return data.result?.[0] ?? {};
  }, [data.loading, data.result]);

  const viewerDataAsObject = useMemo(() => {
    const dataIsPrimitive =
      typeof viewerData !== 'object' ||
      viewerData === null ||
      Array.isArray(viewerData);
    return dataIsPrimitive ? {_result: viewerData} : viewerData;
  }, [viewerData]);

  const originalTableDigest = viewerDataAsObject?.rows?.split('/').pop() ?? '';

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

    const tableUpdateSpecs = convertEditsToTableUpdateSpec();
    const tableUpdateResp = await tableUpdate(
      projectId,
      originalTableDigest,
      tableUpdateSpecs
    );
    const tableRef = `weave:///${projectId}/table/${tableUpdateResp.digest}`;

    const newObjVersion = await objCreate(projectId, objectName, {
      ...objectVersion.val,
      rows: tableRef,
    });

    const url = router.objectVersionUIUrl(
      entityName,
      projectName,
      objectName,
      newObjVersion,
      undefined,
      undefined
    );

    toast(
      <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
        <Icon name="checkmark" width={20} height={20} />
        Published{' '}
        <Link to={url} style={PUBLISHED_LINK_STYLES}>
          {objectName}:v{objectVersionCount}
        </Link>
      </div>
    );
    history.push(url);
    resetEditState();
  }, [
    resetEditState,
    objectVersionCount,
    history,
    router,
    objectName,
    objectVersion.val,
    convertEditsToTableUpdateSpec,
    projectId,
    objCreate,
    tableUpdate,
    originalTableDigest,
    entityName,
    projectName,
  ]);

  const renderEditingControls = () => {
    const editCountStr = String(Array.from(editedRows.keys()).length);
    const addedCountStr = String(addedRows.size);
    const deletedCountStr = String(deletedRows.length);
    return (
      <div className="flex gap-8">
        <div className="mr-8 flex items-center gap-4">
          <Tooltip
            title={`${maybePluralize(Number(editCountStr), 'row')} edited`}
            {...TOOLTIP_PROPS}>
            <div>
              <Pill label={editCountStr} icon="pencil-edit" color="blue" />
            </div>
          </Tooltip>
          <Tooltip
            title={`${maybePluralize(Number(addedCountStr), 'row')} added`}
            {...TOOLTIP_PROPS}>
            <div>
              <Pill label={addedCountStr} icon="add-new" color="green" />
            </div>
          </Tooltip>
          <Tooltip
            title={`${maybePluralize(Number(deletedCountStr), 'row')} deleted`}
            {...TOOLTIP_PROPS}>
            <div>
              <Pill label={deletedCountStr} icon="delete" color="red" />
            </div>
          </Tooltip>
        </div>
        <Button
          title="Cancel"
          tooltip="Cancel"
          variant="secondary"
          size="medium"
          icon="close"
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
            {objectVersionText(objectName, objectVersionIndex)}
          </div>
        </Tailwind>
      }
      headerContent={
        <Tailwind>
          <div className="flex justify-between">
            <div className="grid auto-cols-max grid-flow-col gap-[16px] text-[14px]">
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
            </div>
            <div className="ml-auto mr-0">
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
      tabs={[
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
      ]}
    />
  );
};
