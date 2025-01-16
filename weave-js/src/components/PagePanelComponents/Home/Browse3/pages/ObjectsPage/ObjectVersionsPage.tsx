/**
 * This page is the list-view for object versions. When a single object is selected, it
 * becomes a rich table of versions. It is likely that we will want to outfit it
 * with features similar to the calls table. For example:
 * [ ] Add the ability to expand refs
 * [ ] Paginate & stream responses similar to calls
 * [ ] Add the ability to sort / filter on values
 * [ ] Add the ability to sort / filter on expanded values (blocked by general support for expansion operations)
 * [ ] Add sort / filter state to URL
 */
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import _ from 'lodash';
import React, {useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {Loading} from '../../../../../Loading';
import {useWeaveflowCurrentRouteContext} from '../../context';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {useControllableState} from '../util';
import {DeleteObjectVersionsButtonWithModal} from './ObjectDeleteButtons';
import {WFHighLevelObjectVersionFilter} from './objectsPageTypes';
import {FilterableObjectVersionsTable} from './ObjectVersionsTable';

export const ObjectVersionsPage: React.FC<{
  entity: string;
  project: string;
  initialFilter?: WFHighLevelObjectVersionFilter;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelObjectVersionFilter) => void;
}> = props => {
  const history = useHistory();
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();
  const router = useWeaveflowCurrentRouteContext();
  const [filter, setFilter] = useControllableState(
    props.initialFilter ?? {},
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
    } else if (filter.baseObjectClass) {
      return _.capitalize(filter.baseObjectClass) + 's';
    }
    return 'All Objects';
  }, [filter.objectName, filter.baseObjectClass]);

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
    <SimplePageLayout
      title={title}
      hideTabsIfSingle
      headerExtra={
        <ObjectVersionsPageHeaderExtra
          entity={entity}
          project={project}
          objectName={filter.objectName ?? null}
          selectedVersions={selectedVersions}
          setSelectedVersions={setSelectedVersions}
          showDeleteButton={showDeleteButton}
          showCompareButton={hasComparison}
          onCompare={onCompare}
        />
      }
      tabs={[
        {
          label: '',
          content: (
            <FilterableObjectVersionsTable
              {...props}
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
  );
};

const ObjectVersionsPageHeaderExtra: React.FC<{
  entity: string;
  project: string;
  objectName: string | null;
  selectedVersions: string[];
  setSelectedVersions: (selected: string[]) => void;
  showDeleteButton?: boolean;
  showCompareButton?: boolean;
  onCompare: () => void;
}> = ({
  entity,
  project,
  objectName,
  selectedVersions,
  setSelectedVersions,
  showDeleteButton,
  showCompareButton,
  onCompare,
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
        {compareButton}
        {deleteButton}
      </div>
    </Tailwind>
  );
};
