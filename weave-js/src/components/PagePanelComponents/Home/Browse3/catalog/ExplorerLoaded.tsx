import {ToggleButtonGroup} from '@wandb/weave/components/ToggleButtonGroup';
import {AnimatePresence} from 'motion/react';
import React, {useEffect, useState} from 'react';

import {DropdownSelectSort} from './DropdownSelectSort';
import {ModelTile} from './ModelTile';
import {Model, ModelId, ModelInfo} from './types';
import {getModelProvider} from './util';
import {useHistory} from 'react-router-dom';

type ExplorerLoadedProps = {
  modelInfo: ModelInfo;

  // Collection to filter to
  collectionId?: string;

  // If true, we should create the default target project when navigating to the playground.
  shouldCreateProject: boolean;
};

export const ExplorerLoaded = ({
  modelInfo,
  collectionId,
  shouldCreateProject,
}: ExplorerLoadedProps) => {
  console.log({modelInfo});

  // TODO: Assume you can only pick one of these
  const [filterModality, setFilterModality] = useState('All');
  const [isSortOpen, setIsSortOpen] = useState(false);
  const [sort, setSort] = useState('Popularity');

  const [selected, setSelected] = useState<ModelId[]>([]);
  // TODO: I think we need to keep track of selected that have playground separately

  const [models, setModels] = useState<Model[]>([]);
  useEffect(() => {
    let filteredModels = [...modelInfo.models];

    if (collectionId) {
      // TODO: This should probably be checking an explicit "category" field on the model
      filteredModels = filteredModels.filter(
        m => getModelProvider(m) === collectionId
      );
    }

    if (filterModality !== 'All') {
      filteredModels = filteredModels.filter(
        m => m.modalities && m.modalities.includes(filterModality)
      );
    }

    if (sort === 'Popularity') {
      filteredModels = filteredModels.sort((a, b) => {
        const aPopularity = a.likes ?? 0;
        const bPopularity = b.likes ?? 0;
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

  const onClickTile = (modelId: ModelId) => {
    if (selected.includes(modelId)) {
      setSelected(selected.filter(id => id !== modelId));
    } else {
      setSelected([...selected, modelId]);
    }
  };

  const onClickBackground = () => {
    setSelected([]);
  };

  const history = useHistory();

  const onOpenPlayground = () => {
    // TODO: Fix entity and project
    // TODO: Create project if it doesn't exist
    // TODO: Don't recalculate index
    const modelIndex = modelInfo.models.reduce((acc, m) => {
      acc[m.id] = m;
      return acc;
    }, {} as Record<string, Model>);
    const playgroundIds = selected.map(id => modelIndex[id].id_playground);

    history.push(
      `/jamie-rasmussen/quickstart_playground/weave/playground?${new URLSearchParams(
        playgroundIds.map(modelId => ['model', modelId])
      )}`
    );
  };

  const onCompare = () => {
    history.push(
      `/catalog-compare?${new URLSearchParams(
        selected.map(modelId => ['model', modelId])
      )}`
    );
  };

  return (
    <div className="px-32 py-24" onClick={onClickBackground}>
      <div className="mb-16 flex items-center gap-8">
        <div className="flex-grow text-xl font-semibold">Model catalog</div>
        <ToggleButtonGroup
          options={[
            {value: 'All'},
            {value: 'Text'},
            {value: 'Vision'},
            {value: 'Embedding'},
          ]}
          value={filterModality}
          size="small"
          onValueChange={setFilterModality}
        />

        <DropdownSelectSort
          isOpen={isSortOpen}
          onOpenChange={setIsSortOpen}
          sort={sort}
          setSort={setSort}
        />
      </div>

      <div className="mx-auto grid grid-cols-[500px_500px] justify-center gap-12">
        <AnimatePresence>
          {models.map(m => {
            return (
              <ModelTile
                key={m.id}
                model={m}
                selectedIds={selected}
                onClick={onClickTile}
                onOpenPlayground={onOpenPlayground}
                onCompare={onCompare}
              />
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
};
