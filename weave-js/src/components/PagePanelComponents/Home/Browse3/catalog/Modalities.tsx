import React from 'react';

import {Pill, TagColorName} from '../../../../Tag';

const MODALITY_COLORS: Record<string, TagColorName> = {
  Text: 'gold',
  Vision: 'magenta',
  Embedding: 'cactus',
};

type ModalitiesProps = {
  modalities: string[];
};

export const Modalities = ({modalities}: ModalitiesProps) => {
  return (
    <div className="flex items-center gap-6">
      {modalities.map((m: string) => (
        <Pill key={m} label={m} color={MODALITY_COLORS[m] ?? 'moon'} />
      ))}
    </div>
  );
};
