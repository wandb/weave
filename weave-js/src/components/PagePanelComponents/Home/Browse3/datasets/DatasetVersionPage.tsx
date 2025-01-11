import {Box, Popover, Typography} from '@mui/material';
import React, {useCallback, useMemo, useState} from 'react';
import {Link, useHistory} from 'react-router-dom';
import {toast} from 'react-toastify';

import {Button} from '../../../../Button';
import {Icon} from '../../../../Icon';
import {LoadingDots} from '../../../../LoadingDots';
import {Tailwind} from '../../../../Tailwind';
import {useWeaveflowCurrentRouteContext} from '../context';
import {WeaveCHTableSourceRefContext} from '../pages/CallPage/DataTableView';
import {ObjectVersionsLink, objectVersionText} from '../pages/common/Links';
import {CenteredAnimatedLoader} from '../pages/common/Loader';
import {
  ScrollableTabContent,
  SimplePageLayoutWithHeader,
} from '../pages/common/SimplePageLayout';
import {DeleteObjectButtonWithModal} from '../pages/ObjectVersionPage';
import {TabUseDataset} from '../pages/TabUseDataset';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {TableUpdateSpec} from '../pages/wfReactInterface/traceServerClientTypes';
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

const POPOVER_STYLES = {
  '& .MuiPopover-paper': {
    marginTop: '8px',
    marginRight: '8px',
  },
} as const;

const CODE_STYLES = {
  fontFamily: 'Inconsolata',
  fontWeight: 600,
  backgroundColor: 'rgba(0, 0, 0, 0.04)',
  padding: '2px 4px',
  borderRadius: '4px',
} as const;

export const DatasetVersionPage: React.FC<{
  objectVersion: ObjectVersionSchema;
  showDeleteButton?: boolean;
  refExtra?: string;
}> = ({objectVersion, showDeleteButton, refExtra}) => {
  const {editedCellsMap, editedRows, deletedRows, addedRows} =
    useDatasetEditContext();
  const router = useWeaveflowCurrentRouteContext();
  const {useRootObjectVersions, useRefsData, useTableUpdate, useObjCreate} =
    useWFHooks();

  const [isEditing, setIsEditing] = useState(false);
  const [publishAnchorEl, setPublishAnchorEl] = useState<HTMLElement | null>(
    null
  );

  const entityName = objectVersion.entity;
  const projectName = objectVersion.project;
  const objectName = objectVersion.objectId;
  const objectVersionIndex = objectVersion.versionIndex;
  const projectId = `${entityName}/${projectName}`;

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
  const handleCancelClick = useCallback(() => setIsEditing(false), []);
  const handlePublishClose = () => setPublishAnchorEl(null);

  const handlePublishClick = useCallback(
    (event: React.MouseEvent<HTMLElement>) => {
      if (
        editedCellsMap.size > 0 ||
        deletedRows.length > 0 ||
        addedRows.size > 0
      ) {
        setPublishAnchorEl(event.currentTarget);
      }
    },
    [editedCellsMap, deletedRows, addedRows]
  );

  const cleanRow = (row: any) => {
    return Object.fromEntries(
      Object.entries(row).filter(([key]) => !['___weave'].includes(key))
    );
  };

  const convertEditsToTableUpdateSpec = useCallback(() => {
    const updates: TableUpdateSpec[] = [];

    editedRows.forEach((editedRow, rowIndex) => {
      if (rowIndex !== undefined) {
        updates.push({pop: {index: rowIndex}});
        updates.push({
          insert: {
            index: rowIndex,
            row: cleanRow(editedRow),
          },
        });
      }
    });

    deletedRows
      .sort((a, b) => b - a)
      .forEach(rowIndex => {
        updates.push({pop: {index: rowIndex}});
      });

    Array.from(addedRows.values())
      .reverse()
      .forEach(row => {
        updates.push({
          insert: {
            index: 0,
            row: cleanRow(row),
          },
        });
      });

    return updates;
  }, [editedRows, deletedRows, addedRows]);

  const tableUpdate = useTableUpdate();
  const objCreate = useObjCreate();

  const history = useHistory();

  const handlePublish = useCallback(async () => {
    setIsEditing(false);
    setPublishAnchorEl(null);

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
      refExtra
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
  }, [
    objectVersionCount,
    history,
    refExtra,
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

  const renderEditingControls = () => (
    <div className="flex gap-8">
      <Typography
        variant="body2"
        sx={{
          color: 'text.secondary',
          display: 'flex',
          alignItems: 'center',
          fontSize: '14px',
          fontFamily: 'Source Sans Pro',
          gap: '4px',
        }}>
        <Icon name="pencil-edit" width={14} height={14} />
        Editing dataset
      </Typography>
      <Button
        title="Cancel"
        tooltip="Cancel"
        variant="ghost"
        size="small"
        icon="close"
        onClick={handleCancelClick}>
        Cancel
      </Button>
      <Button
        title="Publish"
        tooltip="Publish"
        size="small"
        variant="primary"
        icon="checkmark"
        onClick={handlePublishClick}
        disabled={
          editedCellsMap.size === 0 &&
          deletedRows.length === 0 &&
          addedRows.size === 0
        }>
        Publish
      </Button>
    </div>
  );

  const renderPublishPopover = () => (
    <Popover
      open={Boolean(publishAnchorEl)}
      anchorEl={publishAnchorEl}
      onClose={handlePublishClose}
      anchorOrigin={{vertical: 'bottom', horizontal: 'right'}}
      transformOrigin={{vertical: 'top', horizontal: 'right'}}
      sx={POPOVER_STYLES}>
      <Box
        sx={{
          p: 3,
          width: 300,
          bgcolor: 'background.paper',
          borderRadius: '8px',
          '& .MuiTypography-root': {fontFamily: 'Source Sans Pro'},
        }}>
        <Typography sx={{mb: 2}}>
          Publish changes to a new version of{' '}
          <code style={CODE_STYLES}>{objectName}</code>?
        </Typography>
        <Box sx={{display: 'flex', justifyContent: 'flex-start', gap: 2}}>
          <Button variant="ghost" onClick={handlePublishClose}>
            Not yet
          </Button>
          <Button
            icon="checkmark"
            variant="primary"
            onClick={() => {
              handlePublish();
              handlePublishClose();
            }}>
            Confirm
          </Button>
        </Box>
      </Box>
    </Popover>
  );

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
                        ({objectVersionCount} version
                        {objectVersionCount !== 1 ? 's' : ''})
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
            {renderPublishPopover()}
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
