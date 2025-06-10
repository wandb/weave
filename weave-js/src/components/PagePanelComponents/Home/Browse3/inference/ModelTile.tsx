/**
 * A tile showing summary information about a model such as provider, cost,
 * and a very brief description.
 */
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React from 'react';

import {Button} from '../../../../Button';
import {IconOnlyPill} from '../../../../Tag';
import {Link} from '../pages/common/Links';
import {Modalities} from './Modalities';
import {InferenceContextType, Model, ModelId, SelectedState} from './types';
import {
  getContextWindowString,
  getDefaultInferenceContext,
  getLaunchDateString,
  getModelLabel,
  getModelLogo,
  getModelSourceName,
  getPriceString,
  urlInference,
} from './util';

type ModelTileProps = {
  model: Model;
  selected?: SelectedState;
  onClick?: (modelId: ModelId) => void;
  onOpenPlayground?: (modelId: ModelId | null) => void;
  inferenceContext?: InferenceContextType;

  // Small text to display at the bottom of the tile.
  hint?: string;
};

export const ModelTile = ({
  model,
  selected,
  onClick,
  onOpenPlayground,
  inferenceContext,
  hint,
}: ModelTileProps) => {
  if (!inferenceContext) {
    inferenceContext = getDefaultInferenceContext();
  }

  const label = getModelLabel(model);
  const logo = getModelLogo(model);
  const logoImg = logo ? (
    <Tooltip
      trigger={<img src={logo} alt="" />}
      content={getModelSourceName(model)}
    />
  ) : null;
  const isSelected =
    selected != null ? selected.selected.includes(model.id) : false;
  const onClickTile = onClick
    ? (e: React.MouseEvent) => {
        e.stopPropagation();
        onClick(model.id);
      }
    : undefined;

  const hasPlayground = !!model.idPlayground && inferenceContext.isLoggedIn;
  const textPlayground =
    selected && selected.selectedWithPlayground.length > 1 && hasPlayground
      ? `Try ${selected.selectedWithPlayground.length} in playground`
      : 'Try in playground';
  const tooltipPlayground = hasPlayground
    ? undefined
    : inferenceContext.isLoggedIn
    ? 'This model is not available in the playground'
    : 'You must be logged in to use the playground';

  const onClickPlayground = onOpenPlayground
    ? (e: React.MouseEvent) => {
        e.stopPropagation();
        onOpenPlayground(
          selected && selected.selectedWithPlayground.length === 0
            ? model.id
            : null
        );
      }
    : undefined;

  // We want to ignore clicks on the button row - it is too easy to
  // unintentionally miss a button and cause tile deselection.
  const onClickButtonRow = (e: React.MouseEvent) => {
    e.stopPropagation();
  };

  return (
    <div
      className={`group w-[500px] cursor-pointer rounded-lg border border-moon-250 bg-white px-16 pb-6 pt-12  ${
        isSelected
          ? 'border-teal-500 shadow-[0_0_10px_rgb(169,237,242)]'
          : 'hover:border-moon-350'
      }`}
      onClick={onClickTile}>
      <div className="mb-8 flex items-center gap-8">
        {logoImg}
        <div className="text-lg font-semibold text-teal-600">
          <Link to={urlInference(model.provider, model.id)}>{label}</Link>
        </div>
        {model.modalities && <Modalities modalities={model.modalities} />}
      </div>
      <div className="mb-8 flex items-center gap-16 text-sm">
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
                <IconOnlyPill color="moon" icon="context-window" />
                <div className="text-moon-500">
                  {getContextWindowString(model)}
                </div>
              </div>
            }
            content="Context window"
          />
        )}
      </div>
      <div className="text-sm text-moon-650">{model.descriptionShort}</div>
      {onClickPlayground && (
        <div
          className={`flex gap-8 py-6 transition-opacity duration-200 ${
            isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
          }`}
          onClick={onClickButtonRow}>
          <Button
            size="small"
            onClick={onClickPlayground}
            disabled={!hasPlayground}
            tooltip={tooltipPlayground}>
            {textPlayground}
          </Button>
        </div>
      )}
      {hint && (
        <div className="py-6 text-sm text-moon-500">
          <i>{hint}</i>
        </div>
      )}
    </div>
  );
};
