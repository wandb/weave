import {ToggleButtonGroup} from '@wandb/weave/components/ToggleButtonGroup';
import {AnimatePresence} from 'motion/react';
import React, {useEffect, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {DropdownSelectSort, ModelTileSortOrder} from './DropdownSelectSort';
import {ModelTileAnimated} from './ModelTileAnimated';
import {navigateToPlayground} from './navigate';
import {
  InferenceContextType,
  Modality,
  Model,
  ModelId,
  ModelInfo,
  SelectedState,
} from './types';

type ExplorerLoadedProps = {
  inferenceContext: InferenceContextType;
  modelInfo: ModelInfo;

  width: number;

  collectionId?: string; // Collection to filter to
};

export const ExplorerLoaded = ({
  modelInfo,
  collectionId,
  width,
  inferenceContext,
}: ExplorerLoadedProps) => {
  const [filterModality, setFilterModality] = useState<Modality | 'All'>('All');
  const [isSortOpen, setIsSortOpen] = useState(false);
  const [sort, setSort] = useState<ModelTileSortOrder>('Popularity');

  const [selectedState, setSelectedState] = useState<SelectedState>({
    selected: [],
    selectedWithPlayground: [],
  });

  const [models, setModels] = useState<Model[]>([]);
  useEffect(() => {
    let filteredModels = [...modelInfo.models];

    if (collectionId) {
      // TODO: This should probably be checking an explicit "category" field on the model
      filteredModels = filteredModels.filter(m => m.provider === collectionId);
    }

    if (filterModality !== 'All') {
      filteredModels = filteredModels.filter(
        m => m.modalities && m.modalities.includes(filterModality)
      );
    }

    if (sort === 'Popularity') {
      filteredModels = filteredModels.sort((a, b) => {
        const aPopularity = a.likesHuggingFace ?? 0;
        const bPopularity = b.likesHuggingFace ?? 0;
        return bPopularity - aPopularity;
      });
    } else if (sort === 'Newest') {
      filteredModels = filteredModels.sort((a, b) => {
        const aDate = a.launchDate ? new Date(a.launchDate).getTime() : 0;
        const bDate = b.launchDate ? new Date(b.launchDate).getTime() : 0;
        return bDate - aDate;
      });
    } else if (sort === 'Input price (low to high)') {
      filteredModels = filteredModels.sort((a, b) => {
        const aPrice = a.priceCentsPerBillionTokensInput ?? 0;
        const bPrice = b.priceCentsPerBillionTokensInput ?? 0;
        return aPrice - bPrice;
      });
    } else if (sort === 'Input price (high to low)') {
      filteredModels = filteredModels.sort((a, b) => {
        const aPrice = a.priceCentsPerBillionTokensInput ?? 0;
        const bPrice = b.priceCentsPerBillionTokensInput ?? 0;
        return bPrice - aPrice;
      });
    } else if (sort === 'Output price (low to high)') {
      filteredModels = filteredModels.sort((a, b) => {
        const aPrice = a.priceCentsPerBillionTokensOutput ?? 0;
        const bPrice = b.priceCentsPerBillionTokensOutput ?? 0;
        return aPrice - bPrice;
      });
    } else if (sort === 'Output price (high to low)') {
      filteredModels = filteredModels.sort((a, b) => {
        const aPrice = a.priceCentsPerBillionTokensOutput ?? 0;
        const bPrice = b.priceCentsPerBillionTokensOutput ?? 0;
        return bPrice - aPrice;
      });
    } else if (sort === 'Biggest context window') {
      filteredModels = filteredModels.sort((a, b) => {
        const aContextWindow = a.contextWindow ?? 0;
        const bContextWindow = b.contextWindow ?? 0;
        return bContextWindow - aContextWindow;
      });
    }

    setModels(filteredModels);
  }, [modelInfo, filterModality, sort, collectionId]);

  // Toggle selection of model when you click on its tile
  const onClickTile = (modelId: ModelId) => {
    const model = models.find(m => m.id === modelId);
    const isSelected = selectedState.selected.includes(modelId);
    const newSelected = isSelected
      ? selectedState.selected.filter(id => id !== modelId)
      : [...selectedState.selected, modelId];

    const newSelectedWithPlayground = isSelected
      ? selectedState.selectedWithPlayground.filter(id => id !== modelId)
      : model?.idPlayground
      ? [...selectedState.selectedWithPlayground, modelId]
      : selectedState.selectedWithPlayground;

    setSelectedState({
      selected: newSelected,
      selectedWithPlayground: newSelectedWithPlayground,
    });
  };

  const onClickBackground = () => {
    setSelectedState({selected: [], selectedWithPlayground: []});
  };

  const history = useHistory();
  const onOpenPlayground = (modelId: ModelId | null) => {
    // If modelId is null, open the selected models.
    navigateToPlayground(
      history,
      modelId ?? selectedState.selectedWithPlayground,
      inferenceContext
    );
  };

  // TODO: Hardcoding number of columns until we can discuss with design team.
  // const availableWidth = width - 2 * 32; // remove padding
  const tileWidth = 500;
  const gap = 12;
  const numColumns = 2;
  // const numColumns = Math.max(
  //   1,
  //   Math.floor((availableWidth + gap) / (tileWidth + gap))
  // );

  return (
    <div className="px-32 py-24" onClick={onClickBackground}>
      <div className="mb-16 flex items-center gap-8">
        <div className="flex-grow text-xl font-semibold">W&B hosted models</div>
        <ToggleButtonGroup
          options={[
            {value: 'All'},
            {value: 'Text'},
            {value: 'Vision'},
            {value: 'Embedding'},
          ]}
          value={filterModality}
          size="small"
          onValueChange={(value: string) =>
            setFilterModality(value as Modality)
          }
        />

        <DropdownSelectSort
          isOpen={isSortOpen}
          onOpenChange={setIsSortOpen}
          sort={sort}
          setSort={setSort}
        />
      </div>

      <div
        style={{
          gridTemplateColumns: `repeat(${numColumns}, ${tileWidth}px)`,
          gap,
        }}
        className="mx-auto grid">
        <AnimatePresence>
          {models.map(m => {
            return (
              <ModelTileAnimated
                key={m.id}
                model={m}
                selected={selectedState}
                onClick={onClickTile}
                onOpenPlayground={onOpenPlayground}
                inferenceContext={inferenceContext}
              />
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
};
