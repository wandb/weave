/**
 * This page is specifically for datasets. It shows a list of dataset objects and their versions.
 * It is inspired by ObjectVersionsPage but tailored specifically for the dataset use case.
 */
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {Loading} from '../../../../../Loading';
import {useWeaveflowCurrentRouteContext} from '../../context';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {DeleteObjectVersionsButtonWithModal} from '../ObjectsPage/ObjectDeleteButtons';
import {WFHighLevelObjectVersionFilter} from '../ObjectsPage/objectsPageTypes';
import {FilterableObjectVersionsTable} from '../ObjectsPage/ObjectVersionsTable';
import {useControllableState} from '../util';
import {DatasetUploadDrawer} from './DatasetUploadDrawer';

export type DatasetFilter = WFHighLevelObjectVersionFilter;

const DATASET_TYPE = 'Dataset' as const;

export const DatasetsPage: React.FC<{
  entity: string;
  project: string;
  initialFilter?: DatasetFilter;
  onFilterUpdate?: (filter: DatasetFilter) => void;
}> = props => {
  const history = useHistory();
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();
  const router = useWeaveflowCurrentRouteContext();
  const [showDatasetUploadDrawer, setShowDatasetUploadDrawer] = useState(false);

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

  const {entity, project} = props;
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

  if (loadingUserInfo) {
    return <Loading />;
  }

  const filteredOnObject = filter.objectName != null;
  const hasComparison = filteredOnObject;
  const viewer = userInfo ? userInfo.id : null;
  const isReadonly = !viewer || !userInfo?.teams.includes(props.entity);
  const isAdmin = userInfo?.admin;
  const showDeleteButton = filteredOnObject && !isReadonly && isAdmin;

  return (
    <React.Fragment>
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
            onUploadButton={() => {
              setShowDatasetUploadDrawer(true);
            }}
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
      <DatasetUploadDrawer
        entity={entity}
        project={project}
        show={showDatasetUploadDrawer}
        onClose={() => setShowDatasetUploadDrawer(false)}
      />
    </React.Fragment>
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
  onUploadButton: () => void;
}> = ({
  entity,
  project,
  objectName,
  selectedVersions,
  setSelectedVersions,
  showDeleteButton,
  showCompareButton,
  onCompare,
  onUploadButton,
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

  const uploadButton = (
    <Button icon="add-new" onClick={onUploadButton}>
      Upload
    </Button>
  );

  return (
    <Tailwind>
      <div className="mr-16 flex gap-8">
        {compareButton}
        {deleteButton}
        {uploadButton}
      </div>
    </Tailwind>
  );
};
