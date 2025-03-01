import {Box, Stack, Typography} from '@mui/material';
import React, {useCallback, useMemo, useState} from 'react';
import {components, GroupBase, MenuListProps} from 'react-select';

import {Checkbox} from '../../../../Checkbox';
import {Select} from '../../../../Form/Select';
import {TextField} from '../../../../Form/TextField';
import {Icon} from '../../../../Icon';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {SmallRef} from '../smallRef/SmallRef';
import {DataPreviewTooltip} from './DataPreviewTooltip';
import {ACTION_TYPES, useDatasetDrawer} from './DatasetDrawerContext';
import {useDatasetEditContext} from './DatasetEditorContext';
import {validateDatasetName} from './datasetNameValidation';

const typographyStyle = {fontFamily: 'Source Sans Pro'};

export interface SelectDatasetStepProps {
  selectedDataset: ObjectVersionSchema | null;
  setSelectedDataset: (dataset: ObjectVersionSchema | null) => void;
  datasets: ObjectVersionSchema[];
  onCreateNewDataset?: (name: string) => void;
  newDatasetName?: string | null;
  setNewDatasetName?: (name: string) => void;
  onValidationChange?: (isValid: boolean) => void;
  entity: string;
  project: string;
  isCreatingNew?: boolean;
  setIsCreatingNew?: (isCreating: boolean) => void;
}

interface DatasetOptionProps {
  dataset: ObjectVersionSchema;
  entity: string;
  project: string;
}

const CREATE_NEW_OPTION_VALUE = '__create_new__';

const DatasetOption: React.FC<DatasetOptionProps> = ({
  dataset,
  entity,
  project,
}) => {
  const {useObjectVersion, useTableRowsQuery} = useWFHooks();

  const datasetObjectVersion = useObjectVersion(
    dataset
      ? {
          scheme: 'weave',
          weaveKind: 'object',
          entity: dataset.entity,
          project: dataset.project,
          objectId: dataset.objectId,
          versionHash: dataset.versionHash,
          path: dataset.path,
        }
      : null,
    undefined
  );

  const tableDigest = datasetObjectVersion.result?.val?.rows?.split('/')?.pop();
  const tableRowsQuery = useTableRowsQuery(
    entity || '',
    project || '',
    tableDigest || '',
    undefined,
    5 // Limit to 5 rows for preview
  );

  const previewRows = tableRowsQuery?.result?.rows.map(row => row.val) || [];
  const isLoading = datasetObjectVersion.loading || tableRowsQuery?.loading;

  return (
    <DataPreviewTooltip
      rows={previewRows}
      isLoading={isLoading}
      tooltipProps={{
        placement: 'right-start',
        componentsProps: {
          popper: {
            modifiers: [
              {
                name: 'offset',
                options: {
                  offset: [0, 2],
                },
              },
            ],
          },
        },
      }}>
      <Box sx={{display: 'flex', alignItems: 'center'}}>
        <SmallRef
          objRef={{
            scheme: 'weave',
            weaveKind: 'object',
            entityName: dataset.entity,
            projectName: dataset.project,
            artifactName: dataset.objectId,
            artifactVersion: dataset.versionHash,
          }}
          noLink
        />
      </Box>
    </DataPreviewTooltip>
  );
};

const CreateNewOption = () => (
  <Box
    sx={{
      display: 'flex',
      alignItems: 'center',
      gap: 1,
      '&:hover': {
        backgroundColor: 'transparent',
      },
    }}>
    <Icon name="add-new" size="small" />
    <Box
      component="span"
      sx={{
        fontSize: '16px',
        fontFamily: 'Source Sans Pro',
        fontWeight: 600,
      }}>
      Create new
    </Box>
  </Box>
);

type DatasetSelectOption =
  | {
      label: JSX.Element;
      value: ObjectVersionSchema;
      searchText: string;
    }
  | {
      label: JSX.Element;
      value: string;
      searchText: string;
    };

const DatasetSelectMenu = (
  props: MenuListProps<
    DatasetSelectOption,
    false,
    GroupBase<DatasetSelectOption>
  >
) => {
  const createNewOption = React.Children.toArray(props.children).find(
    (child: any) => child?.props?.data?.value === CREATE_NEW_OPTION_VALUE
  );
  const otherOptions = React.Children.toArray(props.children).filter(
    (child: any) => child?.props?.data?.value !== CREATE_NEW_OPTION_VALUE
  );

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateRows: 'minmax(0, 1fr) auto',
        height: '100%',
        minHeight: 0,
      }}>
      <Box sx={{minHeight: 0, overflowY: 'auto'}}>
        <components.MenuList {...props} children={otherOptions} />
      </Box>
      <Box
        sx={{
          borderTop: '1px solid',
          borderColor: 'divider',
          bgcolor: 'rgba(0, 0, 0, 0.02)',
          py: 1,
        }}>
        {createNewOption}
      </Box>
    </Box>
  );
};

export const SelectDatasetStep: React.FC<SelectDatasetStepProps> = ({
  selectedDataset,
  setSelectedDataset,
  datasets,
  newDatasetName = '',
  setNewDatasetName = () => {},
  onValidationChange = () => {},
  entity,
  project,
  isCreatingNew = false,
  setIsCreatingNew = () => {},
}) => {
  const [error, setError] = useState<string | null>(null);
  const [showLatestOnly, setShowLatestOnly] = useState(true);
  const {resetEditState} = useDatasetEditContext();
  const {dispatch} = useDatasetDrawer();

  const handleNameChange = (value: string) => {
    setNewDatasetName(value);
    const validationResult = validateDatasetName(value);
    setError(validationResult.error);
    onValidationChange(validationResult.isValid);
  };

  const filteredDatasets = useMemo(() => {
    if (!showLatestOnly) {
      return datasets;
    }

    // Group datasets by objectId and find the latest version for each
    const latestVersions = new Map<string, ObjectVersionSchema>();
    datasets.forEach(dataset => {
      const existing = latestVersions.get(dataset.objectId);
      if (!existing || dataset.versionIndex > existing.versionIndex) {
        latestVersions.set(dataset.objectId, dataset);
      }
    });
    return Array.from(latestVersions.values());
  }, [datasets, showLatestOnly]);

  const dropdownOptions = useMemo(() => {
    const datasetOptions = filteredDatasets.map(dataset => ({
      label: (
        <DatasetOption dataset={dataset} entity={entity} project={project} />
      ),
      value: dataset,
      searchText: dataset.objectId,
    }));

    return [
      ...datasetOptions,
      {
        label: <CreateNewOption />,
        value: CREATE_NEW_OPTION_VALUE,
        searchText: 'create new dataset',
      },
    ];
  }, [filteredDatasets, entity, project]);

  const filterOption = useCallback((option: any, inputValue: string) => {
    return (
      option.data.value === CREATE_NEW_OPTION_VALUE ||
      option.data.searchText.toLowerCase().includes(inputValue.toLowerCase())
    );
  }, []);

  const handleDatasetChange = (option: any) => {
    if (option?.value === CREATE_NEW_OPTION_VALUE) {
      setSelectedDataset(null);
      setIsCreatingNew(true);
      resetEditState();
      // Also clear any error from previous dataset name validation
      setError(null);
      dispatch({type: ACTION_TYPES.SET_ERROR, payload: null});
    } else {
      setSelectedDataset(option?.value ?? null);
      setIsCreatingNew(false);
    }
  };

  return (
    <Stack spacing={'24px'} sx={{mt: '24px'}}>
      <Box>
        <Typography sx={{...typographyStyle, fontWeight: 600, mb: '8px'}}>
          Choose a dataset
        </Typography>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 3,
          }}>
          <Box sx={{flex: '0 1 400px', minWidth: 0}}>
            <Select
              placeholder="Select Dataset"
              value={
                selectedDataset
                  ? dropdownOptions.find(opt => opt.value === selectedDataset)
                  : isCreatingNew
                  ? dropdownOptions.find(
                      opt => opt.value === CREATE_NEW_OPTION_VALUE
                    )
                  : null
              }
              options={dropdownOptions}
              onChange={handleDatasetChange}
              isSearchable={true}
              isClearable={false}
              filterOption={filterOption}
              components={{MenuList: DatasetSelectMenu}}
              maxMenuHeight={300}
            />
          </Box>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}>
            <Checkbox
              checked={showLatestOnly}
              onCheckedChange={checked => setShowLatestOnly(checked === true)}
              size="small"
            />
            <Typography
              onClick={() => setShowLatestOnly(!showLatestOnly)}
              sx={{...typographyStyle, userSelect: 'none', cursor: 'pointer'}}>
              Show latest versions only
            </Typography>
          </Box>
        </Box>
      </Box>

      {isCreatingNew && (
        <Box>
          <Typography sx={{...typographyStyle, fontWeight: 600, mb: '8px'}}>
            Dataset name
          </Typography>
          <TextField
            value={newDatasetName ?? ''}
            onChange={value => {
              handleNameChange(value);
            }}
            placeholder="Enter a name for your new dataset"
            errorState={error != null}
          />
          {error && (
            <Typography
              sx={{
                color: 'error.main',
                fontFamily: 'Source Sans Pro',
                fontSize: '0.875rem',
                mt: 1,
              }}>
              {error}
            </Typography>
          )}
          <Typography
            sx={{
              color: 'text.secondary',
              fontFamily: 'Source Sans Pro',
              fontSize: '0.875rem',
              mt: 1,
            }}>
            Valid dataset names must start with a letter or number and can only
            contain letters, numbers, hyphens, and underscores.
          </Typography>
        </Box>
      )}
    </Stack>
  );
};
