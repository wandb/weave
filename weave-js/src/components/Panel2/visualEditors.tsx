// Shared compoennts and helpers for building visual editors,
// like PanelFilterEditor and PanelGroupEditor

import {isAssignableTo, maybe, Type} from '@wandb/weave/cg';
import {Button} from '@wandb/weave/components/Button';
import React from 'react';

export const getSimpleKeyType = (keyType: Type) => {
  return isAssignableTo(keyType, maybe('string'))
    ? 'string'
    : isAssignableTo(keyType, maybe('number'))
    ? 'number'
    : isAssignableTo(keyType, maybe('boolean'))
    ? 'boolean'
    : 'other';
};

interface VisualEditorModeProps {
  mode: 'visual' | 'expression';
  visualAvailable: boolean;
  setMode: (mode: 'visual' | 'expression') => void;
}

export const VisualEditorMode: React.FC<VisualEditorModeProps> = props => {
  const {visualAvailable, mode, setMode} = props;
  const actualMode = visualAvailable ? mode : 'expression';
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        marginBottom: '8px',
        gap: '4px',
        // This puts the buttons equal with the header
        right: '16px',
        top: '-30px',
        position: 'absolute',
      }}>
      <Button
        variant="ghost"
        size="small"
        disabled={!visualAvailable}
        onClick={() => visualAvailable && setMode('visual')}
        active={actualMode === 'visual'}>
        Visual
      </Button>
      <Button
        variant="ghost"
        size="small"
        onClick={() => setMode('expression')}
        active={actualMode === 'expression'}>
        Expression
      </Button>
    </div>
  );
};
