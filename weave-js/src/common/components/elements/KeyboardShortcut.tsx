import * as globals from '@wandb/weave/common/css/globals.styles';
import React, {FC, memo} from 'react';
import styled from 'styled-components';

type KeyboardShortcutProps = {
  keys: string[];
  lightMode?: boolean;
  className?: string;
};

const KeyboardShortcutComp: FC<KeyboardShortcutProps> = ({
  keys,
  lightMode,
  className,
}) => {
  return (
    <Keys className={className}>
      {keys.map((k, i) => (
        <Key key={i} lightMode={lightMode}>
          {k}
        </Key>
      ))}
    </Keys>
  );
};

export const KeyboardShortcut = memo(KeyboardShortcutComp);

const Keys = styled.div`
  display: inline-flex;
`;

const Key = styled.div<{lightMode?: boolean}>`
  display: inline-block;
  padding: 2px 6px;
  color: ${p => (p.lightMode ? globals.GRAY_500 : globals.GRAY_350)};
  background-color: ${p =>
    p.lightMode
      ? globals.hexToRGB(globals.GRAY_900, 0.04)
      : globals.hexToRGB(globals.MOONBEAM, 0.1)};
  border-radius: 3px;

  &:not(:first-child) {
    margin-left: 1px;
  }
`;
