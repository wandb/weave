/**
 * A wrapper around ModelTile to animate entry/exit. We do not always want this behavior,
 * e.g. if the tile is being used in an informational popup.
 */

import {motion} from 'motion/react';
import React from 'react';

import {ModelTile} from './ModelTile';
import {InferenceContextType, Model, ModelId, SelectedState} from './types';

type ModelTileAnimatedProps = {
  model: Model;
  selected?: SelectedState;
  onClick?: (modelId: ModelId) => void;
  onOpenPlayground?: (modelId: ModelId | null) => void;
  inferenceContext?: InferenceContextType;
};

export const ModelTileAnimated = (props: ModelTileAnimatedProps) => {
  return (
    <motion.div
      layout="position"
      initial={{opacity: 0}}
      animate={{opacity: 1}}
      exit={{opacity: 0}}
      transition={{duration: 0.4}}>
      <ModelTile {...props} />
    </motion.div>
  );
};
