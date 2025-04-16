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

  const handleSaveDataset = async (name: string, rows: any[]) => {
    setIsCreatingDataset(true);
    try {
      // Create the dataset using the actual API function
      const result = await createNewDataset({
        projectId: `${entity}/${project}`,
        entity,
        project,
        datasetName: name,
        rows,
        tableCreate,
        objCreate,
        router,
      });
      toast(
        <DatasetPublishToast
          message={'Dataset created successfully!'}
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
      toast.error(`Failed to create dataset: ${error.message}`);
    } finally {
      setIsCreatingDataset(false);
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
