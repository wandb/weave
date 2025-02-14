import {Box, Paper, Stack, Tooltip, Typography} from '@mui/material';
import React, {useCallback, useEffect, useMemo} from 'react';

import {parseRef} from '../../../../../react';
import {Select} from '../../../../Form/Select';
import {Icon} from '../../../../Icon';
import {LoadingDots} from '../../../../LoadingDots';
import {Pill} from '../../../../Tag/Pill';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {SmallRef} from '../smallRef/SmallRef';
import {
  CallData,
  extractSourceSchema,
  FieldMapping,
  inferSchema,
  suggestMappings,
} from './schemaUtils';

export interface SchemaMappingStepProps {
  selectedDataset: ObjectVersionSchema;
  selectedCalls: CallData[];
  entity: string;
  project: string;
  onMappingChange: (mappings: FieldMapping[]) => void;
  onDatasetObjectLoaded: (obj: any) => void;
  fieldMappings?: FieldMapping[];
  datasetObject?: any;
}

const typographyStyle = {fontFamily: 'Source Sans Pro'};

export const SchemaMappingStep: React.FC<SchemaMappingStepProps> = ({
  selectedDataset,
  selectedCalls,
  entity,
  project,
  onMappingChange,
  onDatasetObjectLoaded,
  fieldMappings,
}) => {
  const {useObjectVersion, useTableRowsQuery} = useWFHooks();
  const scrollRef = React.useRef<HTMLDivElement>(null);

  const sourceSchema = useMemo(() => {
    return selectedCalls.length > 0 ? extractSourceSchema(selectedCalls) : [];
  }, [selectedCalls]);

  const selectedDatasetObjectVersion = useObjectVersion(
    selectedDataset
      ? {
          scheme: 'weave',
          weaveKind: 'object',
          entity: selectedDataset.entity,
          project: selectedDataset.project,
          objectId: selectedDataset.objectId,
          versionHash: selectedDataset.versionHash,
          path: selectedDataset.path,
        }
      : null,
    undefined
  );

  useEffect(() => {
    if (selectedDatasetObjectVersion.result?.val) {
      onDatasetObjectLoaded(selectedDatasetObjectVersion.result.val);
    }
  }, [selectedDatasetObjectVersion.result, onDatasetObjectLoaded]);

  const tableDigest = selectedDatasetObjectVersion.result?.val?.rows
    ?.split('/')
    ?.pop();

  const tableRowsQuery = useTableRowsQuery(
    entity || '',
    project || '',
    tableDigest || ''
  );

  const targetSchema = useMemo(() => {
    if (!tableRowsQuery.result) {
      return [];
    }
    return inferSchema(tableRowsQuery.result.rows.map(row => row.val));
  }, [tableRowsQuery.result]);

  const localFieldMappings = useMemo(() => {
    if (!tableRowsQuery.result || !targetSchema.length) {
      return fieldMappings || [];
    }
    return suggestMappings(sourceSchema, targetSchema, fieldMappings || []);
  }, [sourceSchema, targetSchema, fieldMappings, tableRowsQuery.result]);

  useEffect(() => {
    if (JSON.stringify(localFieldMappings) !== JSON.stringify(fieldMappings)) {
      onMappingChange(localFieldMappings);
    }
  }, [localFieldMappings, fieldMappings, onMappingChange]);

  const handleMappingChange = useCallback(
    (targetField: string, sourceField: string | null) => {
      const existingMappings = fieldMappings || [];
      const newMappings = [...existingMappings, ...localFieldMappings].filter(
        m => m.targetField !== targetField
      );

      if (sourceField) {
        newMappings.push({sourceField, targetField});
      }
      onMappingChange(newMappings);
    },
    [localFieldMappings, fieldMappings, onMappingChange]
  );

  if (
    tableRowsQuery.loading ||
    selectedDatasetObjectVersion.loading ||
    !targetSchema.length
  ) {
    return (
      <Stack spacing={1} sx={{mt: 2}}>
        <Typography sx={{...typographyStyle, fontWeight: 600}}>
          Field Mapping
        </Typography>
        <Paper
          variant="outlined"
          sx={{
            p: 2,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: '56px',
          }}>
          <LoadingDots />
        </Paper>
      </Stack>
    );
  }

  if (!selectedCalls.length || !tableRowsQuery.result?.rows?.length) {
    return (
      <Stack spacing={1} sx={{mt: 2}}>
        <Typography sx={typographyStyle}>
          No data available to extract schema from.
        </Typography>
      </Stack>
    );
  }

  if (!sourceSchema.length || !targetSchema.length) {
    return (
      <Stack spacing={1} sx={{mt: 2}}>
        <Typography sx={typographyStyle}>
          No schema could be extracted from the data.
        </Typography>
      </Stack>
    );
  }

  return (
    <Stack spacing={1} sx={{mt: 2}}>
      <Typography sx={{...typographyStyle, fontWeight: 600}}>
        Field mapping
      </Typography>
      <Paper variant="outlined" sx={{p: 2}}>
        <Box display="flex" alignItems="flex-start" gap={2}>
          <Box
            sx={{
              position: 'relative',
              flex: 1,
              minWidth: '100px',
              display: 'flex',
              alignItems: 'flex-start',
            }}>
            <Box
              ref={scrollRef}
              display="flex"
              gap={1}
              sx={{
                width: '100%',
                flexWrap: 'wrap',
                maxHeight: '192px',
                overflowY: 'auto',
              }}>
              {Array.from(
                new Set(selectedCalls.map(call => call.val.op_name))
              ).map(opName => (
                <Box
                  key={opName}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    flexWrap: 'wrap',
                  }}>
                  {(() => {
                    try {
                      return <SmallRef objRef={parseRef(opName)} />;
                    } catch (e: any) {
                      return (
                        <Tooltip title={e.message} arrow>
                          <Box>
                            <Pill
                              label="Error"
                              icon="warning"
                              color="red"
                              className="rounded py-2 text-xs font-semibold"
                            />
                          </Box>
                        </Tooltip>
                      );
                    }
                  })()}
                </Box>
              ))}
            </Box>
            <Box
              sx={{
                position: 'absolute',
                left: 0,
                top: 0,
                bottom: 0,
                width: '32px',
              }}
            />
            <Box
              sx={{
                position: 'absolute',
                right: 0,
                top: 0,
                bottom: 0,
                width: '32px',
              }}
            />
          </Box>
          <Box
            sx={{
              width: '40px',
              flexShrink: 0,
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'flex-start',
              paddingTop: '8px',
            }}>
            <Icon name="forward-next" />
          </Box>
          <Box
            sx={{
              flex: 1,
              minWidth: '100px',
              paddingTop: '4px',
            }}>
            <SmallRef
              objRef={{
                scheme: 'weave',
                weaveKind: 'object',
                entityName: selectedDataset.entity,
                projectName: selectedDataset.project,
                artifactName: selectedDataset.objectId,
                artifactVersion: selectedDataset.versionHash,
              }}
            />
          </Box>
        </Box>
      </Paper>
      <Paper variant="outlined" sx={{p: 2, bgcolor: '#F8F8F8'}}>
        <Stack spacing={1}>
          {targetSchema.map(targetField => {
            const currentMapping = localFieldMappings.find(
              m => m.targetField === targetField.name
            );

            return (
              <Box
                key={targetField.name}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 2,
                  height: '40px',
                }}>
                <Box sx={{flex: 1, minWidth: '100px'}}>
                  <Select
                    placeholder="Select column"
                    value={
                      currentMapping
                        ? {
                            label: currentMapping.sourceField,
                            value: currentMapping.sourceField,
                          }
                        : null
                    }
                    options={[
                      {label: '-- None --', value: ''},
                      ...sourceSchema.map(field => ({
                        label: field.name,
                        value: field.name,
                      })),
                    ]}
                    onChange={option =>
                      handleMappingChange(
                        targetField.name,
                        option?.value ?? null
                      )
                    }
                  />
                </Box>
                <Box
                  sx={{
                    width: '40px',
                    flexShrink: 0,
                    display: 'flex',
                    justifyContent: 'center',
                  }}>
                  <Icon name="forward-next" />
                </Box>
                <Box sx={{flex: 1, minWidth: '100px'}}>
                  <Typography sx={{...typographyStyle}}>
                    {targetField.name}
                  </Typography>
                </Box>
              </Box>
            );
          })}
        </Stack>
      </Paper>
    </Stack>
  );
};
