import {Box, Paper, Stack, Typography, Tooltip} from '@mui/material';
import React, {useEffect, useState} from 'react';

import {parseRef} from '../../../../../react';
import {Select} from '../../../../Form/Select';
import {Icon} from '../../../../Icon';
import {CopyableId} from '../pages/common/Id';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {SmallRef} from '../smallRef/SmallRef';
import {Pill} from '../../../../Tag/Pill';
import {
  CallData,
  extractSourceSchema,
  FieldMapping,
  inferSchema,
  SchemaField,
  suggestMappings,
} from './schemaUtils';
import {LoadingDots} from '../../../../LoadingDots';

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
  const [sourceSchema, setSourceSchema] = useState<SchemaField[]>([]);
  const [targetSchema, setTargetSchema] = useState<SchemaField[]>([]);
  const [localFieldMappings, setLocalFieldMappings] = useState<FieldMapping[]>(
    fieldMappings || []
  );
  const scrollRef = React.useRef<HTMLDivElement>(null);

  const {useObjectVersion, useTableRowsQuery} = useWFHooks();

  // Extract schema from calls data
  useEffect(() => {
    if (selectedCalls.length > 0) {
      setSourceSchema(extractSourceSchema(selectedCalls));
    }
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

  useEffect(() => {
    if (tableRowsQuery.result) {
      const schema = inferSchema(
        tableRowsQuery.result.rows.map(row => row.val)
      );
      setTargetSchema(schema);

      setLocalFieldMappings(prev =>
        suggestMappings(sourceSchema, schema, prev)
      );
    }
  }, [tableRowsQuery.result, sourceSchema]);

  useEffect(() => {
    onMappingChange(localFieldMappings);
  }, [localFieldMappings, onMappingChange]);

  const handleMappingChange = (
    targetField: string,
    sourceField: string | null
  ) => {
    setLocalFieldMappings(prev => {
      const newMappings = prev.filter(m => m.targetField !== targetField);
      if (sourceField) {
        newMappings.push({sourceField, targetField});
      }
      return newMappings;
    });
  };

  // Sync local state with provided prop whenever it changes (e.g. when navigating back)
  useEffect(() => {
    if (fieldMappings) {
      setLocalFieldMappings(fieldMappings);
    }
  }, [fieldMappings]);

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
        <Paper variant="outlined" sx={{p: 2, display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '56px'}}>
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
              {Object.entries(
                selectedCalls.reduce((acc, call) => {
                  const opName = call.val.op_name;
                  if (!acc[opName]) {
                    acc[opName] = [];
                  }
                  acc[opName].push(call);
                  return acc;
                }, {} as Record<string, CallData[]>)
              ).map(([opName, calls]) => (
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
                    } catch (e) {
                      return (
                        <Tooltip title={e.message} arrow>
                          <Box>
                            <Pill
                              label="Error"
                              icon="warning"
                              color="red"
                              className="text-xs font-semibold py-2 rounded"
                            />
                          </Box>
                        </Tooltip>
                      );
                    }
                  })()}
                  {calls.map(call => (
                    <CopyableId key={call.digest} id={call.digest} />
                  ))}
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
          <Box sx={{
            flex: 1,
            minWidth: '100px',
            paddingTop: '4px'
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
