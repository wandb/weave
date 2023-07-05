import {produce} from 'immer';
import React, {useCallback, useMemo} from 'react';

import {useNodeWithServerType} from '../../../react';
import * as ConfigPanel from '../ConfigPanel';
import * as Panel2 from '../panel';
import * as TableType from '../PanelTable/tableType';
import * as PTypes from './types';
import * as PUtil from './util';

type PanelProjectionConverterProps = Panel2.PanelProps<
  typeof PTypes.inputType,
  PTypes.PanelProjectionConverterConfigType
>;

const MIN_ITER = 500;

const ALGO_OPTIONS = [
  {
    text: 'PCA',
    value: 'pca',
  },
  {
    text: 't-SNE',
    value: 'tsne',
  },
  {
    text: 'UMAP',
    value: 'umap',
  },
];

const FIELD_TYPE_OPTIONS = [
  {
    value: 'single',
    text: 'Single Embedding Column',
  },
  {
    value: 'multiple',
    text: 'Many Numeric Columns',
  },
];

export const PanelProjectionConverter: React.FC<
  PanelProjectionConverterProps
> = props => {
  throw new Error('PanelProjectionConverter: cannot be rendered directly');
};

export const PanelProjectionConverterConfig: React.FC<
  PanelProjectionConverterProps
> = props => {
  if (TableType.isTableTypeLike(props.input.type)) {
    return <PanelProjectionConverterTableConfig {...(props as any)} />;
  } else {
    return <PanelProjectionConverterConfigInner {...(props as any)} />;
  }
};

const PanelProjectionConverterTableConfig: React.FC<
  Panel2.PanelProps<
    typeof TableType.ConvertibleToDataTableType,
    PTypes.PanelProjectionConverterConfigType
  >
> = props => {
  const {input} = props;
  const normalizedInput = useMemo(() => {
    return TableType.normalizeTableLike(input);
  }, [input]);
  const typedNormalizedInput = useNodeWithServerType(normalizedInput);

  if (typedNormalizedInput.loading) {
    return <></>;
  } else if (typedNormalizedInput.result.nodeType === 'void') {
    return <>Input node returned void type</>;
  } else {
    return (
      <PanelProjectionConverterConfigInner
        {...({...props, input: typedNormalizedInput.result} as any)}
      />
    );
  }
};

const PanelProjectionConverterConfigInner: React.FC<
  Panel2.PanelProps<
    typeof PTypes.ProjectableType,
    PTypes.PanelProjectionConverterConfigType
  >
> = props => {
  const {input, config, updateConfig} = props;
  const pConfig = useMemo(() => {
    let processedConfig = PUtil.processConfig<typeof PTypes.ProjectableType>(
      config,
      input
    );
    // migration to reflect the new minimum number of iterations
    // for t-SNE (https://github.com/wandb/weave-internal/pull/731)
    if (
      processedConfig.projectionAlgorithm === 'tsne' &&
      processedConfig?.algorithmOptions?.tsne?.iterations < MIN_ITER
    ) {
      processedConfig = produce(processedConfig, draft => {
        draft.algorithmOptions.tsne.iterations = MIN_ITER;
      });
    }
    return processedConfig;
  }, [config, input]);
  const {validEmbeddingColumns, validNumericColumns} = useMemo(
    () => PUtil.getValidColumns(input.type),
    [input]
  );

  const columnOptions = useMemo(() => {
    return (
      pConfig.inputCardinality === 'multiple'
        ? validNumericColumns
        : validEmbeddingColumns
    ).map(name => ({
      value: name,
      text: name,
    }));
  }, [pConfig.inputCardinality, validNumericColumns, validEmbeddingColumns]);

  const currentColumnOption = useMemo(() => {
    return pConfig.inputCardinality === 'multiple'
      ? pConfig.inputColumnNames
      : pConfig.inputColumnNames.length > 0
      ? pConfig.inputColumnNames[0]
      : undefined;
  }, [pConfig]);

  // TODO: Make this a common utility function - many panels will benefit
  const updateConfigField = useCallback(
    (fieldName: string | string[]) => {
      const fields = Array.isArray(fieldName) ? fieldName : [fieldName];
      return (value: any) => {
        const rootUpdate: {[key: string]: any} = {};
        let update = rootUpdate;
        fields.forEach((field, ndx) => {
          if (ndx === fields.length - 1) {
            update[field] = value;
          } else {
            if (ndx === 0) {
              update[field] = {...((config ?? ({} as any))[field] ?? {})};
            } else {
              update[field] = {...(update[field] ?? {})};
            }
            update = update[field];
          }
        });
        updateConfig(rootUpdate);
      };
    },
    [config, updateConfig]
  );

  const updateConfigFieldFromEvent = useCallback(
    (fieldName: string | string[]) => {
      return (event: any, data: any) => {
        updateConfigField(fieldName)(data.value);
      };
    },
    [updateConfigField]
  );

  return (
    <>
      <ConfigPanel.ConfigOption label={'Algo'}>
        <ConfigPanel.ModifiedDropdownConfigField
          selection
          scrolling
          multiple={false}
          options={ALGO_OPTIONS}
          value={pConfig.projectionAlgorithm}
          onChange={updateConfigFieldFromEvent('projectionAlgorithm')}
        />
      </ConfigPanel.ConfigOption>
      {pConfig.projectionAlgorithm === 'tsne' && (
        <>
          <ConfigPanel.ConfigOption label={'Perplexity'}>
            <ConfigPanel.NumberInputConfigField
              min={0}
              max={1000}
              stepper
              strideLength={1}
              value={pConfig?.algorithmOptions?.tsne?.perplexity}
              onChange={updateConfigField([
                'algorithmOptions',
                'tsne',
                'perplexity',
              ])}
            />
          </ConfigPanel.ConfigOption>
          <ConfigPanel.ConfigOption label={'Learning Rate'}>
            <ConfigPanel.NumberInputConfigField
              min={0}
              stepper
              strideLength={1}
              max={5000}
              value={pConfig?.algorithmOptions?.tsne?.learningRate}
              onChange={updateConfigField([
                'algorithmOptions',
                'tsne',
                'learningRate',
              ])}
            />
          </ConfigPanel.ConfigOption>
          <ConfigPanel.ConfigOption label={'Iterations'}>
            <ConfigPanel.NumberInputConfigField
              min={500}
              max={1000}
              stepper
              strideLength={1}
              value={pConfig?.algorithmOptions?.tsne?.iterations}
              onChange={updateConfigField([
                'algorithmOptions',
                'tsne',
                'iterations',
              ])}
            />
          </ConfigPanel.ConfigOption>
        </>
      )}
      {pConfig.projectionAlgorithm === 'umap' && (
        <>
          <ConfigPanel.ConfigOption label={'Neighbors'}>
            <ConfigPanel.NumberInputConfigField
              min={0}
              max={1000}
              stepper
              strideLength={1}
              value={pConfig?.algorithmOptions?.umap?.neighbors}
              onChange={updateConfigField([
                'algorithmOptions',
                'umap',
                'neighbors',
              ])}
            />
          </ConfigPanel.ConfigOption>
          <ConfigPanel.ConfigOption label={'Min Dist'}>
            <ConfigPanel.NumberInputConfigField
              min={0}
              max={1000}
              stepper
              strideLength={1}
              value={pConfig?.algorithmOptions?.umap?.minDist}
              onChange={updateConfigField([
                'algorithmOptions',
                'umap',
                'minDist',
              ])}
            />
          </ConfigPanel.ConfigOption>
          <ConfigPanel.ConfigOption label={'Spread'}>
            <ConfigPanel.NumberInputConfigField
              min={0}
              max={1000}
              stepper
              strideLength={1}
              value={pConfig?.algorithmOptions?.umap?.spread}
              onChange={updateConfigField([
                'algorithmOptions',
                'umap',
                'spread',
              ])}
            />
          </ConfigPanel.ConfigOption>
        </>
      )}
      <ConfigPanel.ConfigOption label={'Field Type'}>
        <ConfigPanel.ModifiedDropdownConfigField
          selection
          scrolling
          multiple={false}
          options={FIELD_TYPE_OPTIONS}
          value={pConfig.inputCardinality}
          onChange={updateConfigFieldFromEvent('inputCardinality')}
        />
      </ConfigPanel.ConfigOption>
      <ConfigPanel.ConfigOption
        label={`Field${pConfig.inputCardinality === 'multiple' ? 's' : ''}`}>
        <ConfigPanel.ModifiedDropdownConfigField
          selection
          scrolling
          multiple={pConfig.inputCardinality === 'multiple'}
          options={columnOptions}
          value={currentColumnOption}
          onChange={updateConfigFieldFromEvent('inputColumnNames')}
        />
      </ConfigPanel.ConfigOption>
    </>
  );
};
