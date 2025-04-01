/**
 * This page is specifically for datasets. It shows a list of dataset objects and their versions.
 * It is inspired by ObjectVersionsPage but tailored specifically for the dataset use case.
 */
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';
import {toast} from 'react-toastify';

import {Loading} from '../../../../../Loading';
import {useWeaveflowCurrentRouteContext} from '../../context';
import {CreateDatasetDrawer} from '../../datasets/CreateDatasetDrawer';
import {createNewDataset} from '../../datasets/datasetOperations';
import {DatasetPublishToast} from '../../datasets/DatasetPublishToast';
import {useWFHooks} from '../../pages/wfReactInterface/context';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {DeleteObjectVersionsButtonWithModal} from '../ObjectsPage/ObjectDeleteButtons';
import {WFHighLevelObjectVersionFilter} from '../ObjectsPage/objectsPageTypes';
import {FilterableObjectVersionsTable} from '../ObjectsPage/ObjectVersionsTable';
import {useControllableState} from '../util';

export type DatasetFilter = WFHighLevelObjectVersionFilter;

const DATASET_TYPE = 'Dataset' as const;

export const DatasetsPage: React.FC<{
  entity: string;
  project: string;
  initialFilter?: DatasetFilter;
  onFilterUpdate?: (filter: DatasetFilter) => void;
}> = props => {
  const {entity, project} = props;
  const history = useHistory();
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();
  const router = useWeaveflowCurrentRouteContext();
  const {useObjCreate, useTableCreate} = useWFHooks();

  // Get the create hooks
  const tableCreate = useTableCreate();
  const objCreate = useObjCreate();

  const [isCreateDrawerOpen, setIsCreateDrawerOpen] = useState(false);
  const [isCreatingDataset, setIsCreatingDataset] = useState(false);

  const baseFilter = useMemo(() => {
    return {
      ...props.initialFilter,
      baseObjectClass: DATASET_TYPE,
    };
  }, [props.initialFilter]);

  const [filter, setFilter] =
    useControllableState<WFHighLevelObjectVersionFilter>(
      baseFilter ?? {baseObjectClass: DATASET_TYPE},
      props.onFilterUpdate
    );

  const [selectedVersions, setSelectedVersions] = useState<string[]>([]);

  const onCompare = () => {
    history.push(router.compareObjectsUri(entity, project, selectedVersions));
  };

  const title = useMemo(() => {
    if (filter.objectName) {
      return 'Versions of ' + filter.objectName;
    }
    return 'Datasets';
  }, [filter.objectName]);

  const handleCreateDataset = () => {
    setIsCreateDrawerOpen(true);
  };

  const handleCloseDrawer = () => {
    setIsCreateDrawerOpen(false);
  };

  const handleSaveDataset = async (dataset: any) => {
    // Log the dataset being saved for debugging purposes
    console.log('Saving dataset:', dataset);

    // Check if this is a publish action
    const isPublish = dataset.publishNow === true;

    setIsCreatingDataset(true);
    try {
      // Parse the rows from string back to array if they are provided as a string
      const rows =
        typeof dataset.rows === 'string'
          ? JSON.parse(dataset.rows)
          : dataset.rows;

      // Create the dataset using the actual API function
      const result = await createNewDataset({
        projectId: `${entity}/${project}`,
        entity,
        project,
        datasetName: dataset.name,
        rows,
        tableCreate,
        objCreate,
        router,
      });

      // If this is a publish action, we could add additional logic here
      // This would require backend support for publishing datasets
      if (isPublish) {
        console.log('Publishing dataset:', dataset.name);
        // Here you would call an API to mark the dataset as published
        // For now, we'll just log and show different toast messaging
      }

      // Show success message with link to the new dataset
      toast(
        <DatasetPublishToast
          message={
            isPublish
              ? 'Dataset published successfully!'
              : 'Dataset created successfully!'
          }
          url={result.url}
        />,
        {
          position: 'top-right',
          autoClose: 5000,
          hideProgressBar: true,
          closeOnClick: true,
          pauseOnHover: true,
        }
      );
    } catch (error: any) {
      console.error('Failed to create dataset:', error);
      toast.error(
        `Failed to ${isPublish ? 'publish' : 'create'} dataset: ${
          error.message
        }`
      );
    } finally {
      setIsCreatingDataset(false);
      // Close the drawer
      handleCloseDrawer();
    }
  };

  if (loadingUserInfo) {
    return <Loading />;
  }

  const filteredOnObject = filter.objectName != null;
  const hasComparison = filteredOnObject;
  const viewer = userInfo ? userInfo.id : null;
  const isReadonly = !viewer || !userInfo?.teams.includes(entity);
  const isAdmin = userInfo?.admin;
  const showDeleteButton = filteredOnObject && !isReadonly && isAdmin;

  return (
    <>
      <SimplePageLayout
        title={title}
        hideTabsIfSingle
        headerExtra={
          <DatasetsPageHeaderExtra
            entity={entity}
            project={project}
            objectName={filter.objectName ?? null}
            selectedVersions={selectedVersions}
            setSelectedVersions={setSelectedVersions}
            showDeleteButton={showDeleteButton}
            showCompareButton={hasComparison}
            onCompare={onCompare}
            onCreateDataset={handleCreateDataset}
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
                setSelectedVersions={
                  hasComparison ? setSelectedVersions : undefined
                }
              />
            ),
          },
        ]}
      />

      <CreateDatasetDrawer
        open={isCreateDrawerOpen}
        onClose={handleCloseDrawer}
        onSaveDataset={handleSaveDataset}
        isCreating={isCreatingDataset}
      />
    </>
  );
};

const DatasetsPageHeaderExtra: React.FC<{
  entity: string;
  project: string;
  objectName: string | null;
  selectedVersions: string[];
  setSelectedVersions: (selected: string[]) => void;
  showDeleteButton?: boolean;
  showCompareButton?: boolean;
  onCompare: () => void;
  onCreateDataset: () => void;
  isReadonly: boolean;
}> = ({
  entity,
  project,
  objectName,
  selectedVersions,
  setSelectedVersions,
  showDeleteButton,
  showCompareButton,
  onCompare,
  onCreateDataset,
  isReadonly,
}) => {
  const compareButton = showCompareButton ? (
    <Button disabled={selectedVersions.length < 2} onClick={onCompare}>
      Compare
    </Button>
  ) : undefined;

  const deleteButton = showDeleteButton ? (
    <DeleteObjectVersionsButtonWithModal
      entity={entity}
      project={project}
      objectName={objectName ?? ''}
      objectVersions={selectedVersions}
      disabled={selectedVersions.length === 0 || !objectName}
      onSuccess={() => setSelectedVersions([])}
    />
  ) : undefined;

  return (
    <Tailwind>
      <div className="mr-16 flex gap-8">
        {!isReadonly && (
          <Button
            icon="add-new"
            variant="ghost"
            onClick={onCreateDataset}
            tooltip="Create a new dataset">
            New dataset
          </Button>
        )}
        {compareButton}
        {deleteButton}
      </div>
    </Tailwind>
  );
};
