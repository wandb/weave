/**
 * A model can have multiple modalities, display them as a list of pills.
 */
import React from 'react';

import {Pill, TagColorName} from '../../../../Tag';
import {Modality} from './types';

const MODALITY_COLORS: Record<Modality, TagColorName> = {
  Text: 'gold',
  Vision: 'magenta',
  Embedding: 'cactus',
};

type ModalitiesProps = {
  modalities: Modality[];
};

export const Modalities = ({modalities}: ModalitiesProps) => {
  return (
    <div className="flex items-center gap-6">
      {modalities.map((m: Modality) => (
        <Pill key={m} label={m} color={MODALITY_COLORS[m] ?? 'moon'} />
      ))}
    </div>
  );
};
