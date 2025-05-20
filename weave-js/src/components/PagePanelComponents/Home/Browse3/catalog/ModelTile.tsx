import {Tooltip} from '@wandb/weave/components/Tooltip';
import {motion} from 'motion/react';
import React from 'react';

import {Button} from '../../../../Button';
import {IconOnlyPill} from '../../../../Tag';
import {Link} from '../pages/common/Links';
import {Modalities} from './Modalities';
import {Model, ModelId} from './types';
import {
  getContextWindowString,
  getLaunchDateString,
  getModelLabel,
  getModelLogo,
  getModelProviderName,
  getPriceString,
} from './util';

type ModelTileProps = {
  model: Model;
  selectedIds: ModelId[];
  onClick: (modelId: ModelId) => void;
  onOpenPlayground: () => void;
  onCompare: () => void;
};

export const ModelTile = ({
  model,
  selectedIds,
  onClick,
  onOpenPlayground,
  onCompare,
}: ModelTileProps) => {
  const label = getModelLabel(model);
  const logo = getModelLogo(model);
  const logoImg = logo ? (
    <Tooltip
      trigger={<img src={logo} alt="" />}
      content={getModelProviderName(model)}
    />
  ) : null;
  const isSelected = selectedIds.includes(model.id);
  const onClickTile = (e: React.MouseEvent) => {
    e.stopPropagation();
    onClick(model.id);
  };

  const hasPlayground = !!model.id_playground;
  const textPlayground =
    selectedIds.length > 1 && hasPlayground
      ? `Try ${selectedIds.length} in playground`
      : 'Try in playground';
  const tooltipPlayground = hasPlayground
    ? undefined
    : 'This model is not available in the playground';

  const onClickPlayground = (e: React.MouseEvent) => {
    e.stopPropagation();
    onOpenPlayground();
  };

  const onClickCompare = (e: React.MouseEvent) => {
    e.stopPropagation();
    onCompare();
  };

  return (
    <motion.div
      layout="position"
      initial={{opacity: 0}}
      animate={{opacity: 1}}
      exit={{opacity: 0}}
      transition={{duration: 0.4}}
      className={`group w-[500px] cursor-pointer rounded-lg border border-moon-200 bg-white px-16 py-12 ${
        isSelected ? 'shadow-[0_0_10px_rgb(169,237,242)]' : ''
      }`}
      onClick={onClickTile}>
      <div className="flex cursor-pointer items-center gap-8">
        {/* <Orb /> */}
        {logoImg}
        <div className="text-md font-semibold text-teal-600">
          <Link to={`/catalog/${model.provider}/${model.id}`}>{label}</Link>
        </div>
        {model.modalities && <Modalities modalities={model.modalities} />}
      </div>
      <div className="flex items-center gap-16">
        {model.launchDate && (
          <Tooltip
            trigger={
              <div className="flex items-center gap-2">
                <IconOnlyPill color="moon" icon="date" />
                <div className="text-moon-500">
                  {getLaunchDateString(model)}
                </div>
              </div>
            }
            content="Model release date"
          />
        )}
        {(model.priceCentsPerBillionTokensInput ||
          model.priceCentsPerBillionTokensOutput) && (
          <Tooltip
            trigger={
              <div className="flex items-center gap-2">
                <IconOnlyPill color="moon" icon="credit-card-payment" />
                <div className="text-moon-500">{getPriceString(model)}</div>
              </div>
            }
            content="Price per million tokens"
          />
        )}
        {model.contextWindow && (
          <Tooltip
            trigger={
              <div className="flex items-center gap-2">
                <IconOnlyPill color="moon" icon="recent-clock" />
                <div className="text-moon-500">
                  {getContextWindowString(model.contextWindow)}
                </div>
              </div>
            }
            content="Context window"
          />
        )}
      </div>
      <div className="text-sm text-moon-650">{model.descriptionShort}</div>
      <div
        className={`mt-12 flex gap-8 transition-opacity duration-200 ${
          isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
        }`}>
        <Button
          size="small"
          onClick={onClickPlayground}
          disabled={!hasPlayground}
          tooltip={tooltipPlayground}>
          {textPlayground}
        </Button>
        {isSelected && selectedIds.length >= 2 && (
          <Button size="small" onClick={onClickCompare}>
            <span>Compare {selectedIds.length} models</span>
          </Button>
        )}
        <Button
          variant="secondary"
          size="small"
          onClick={e => e.stopPropagation()}>
          Evaluate model
        </Button>
      </div>
    </motion.div>
  );
};
