import React from 'react';
import styled from 'styled-components';

import {IconHelpAlt} from '../Icon';
import * as LE from './Home/LayoutElements';

const HelpCTAOuter = styled(LE.HStack)`
  position: absolute;
  bottom: 16px;
  left: 0px;
  z-index: 1000;
  width: 300px;
  height: 48px;
  justify-content: center;
`;
HelpCTAOuter.displayName = 'S.HelpCTAOuter';

const HelpCTAInner = styled(LE.HStack)`
  padding: 0px 16px;
  height: 40px;
  gap: 10px;
  border-radius: 20px;
  background-color: #ffe49e80;
  color: #b8740f;
  align-items: center;
  line-height: 16px;
  font-weight: 400;
  width: fit-content;
  cursor: pointer;
  transition: all 0.2s ease-in-out;
  &:hover {
    background-color: #ffe49e;
  }
`;
HelpCTAInner.displayName = 'S.HelpCTAInner';

const HELP_LINK = 'https://wandb.me/prompts-discord';

export const HelpCTA: React.FC<{}> = () => {
  return (
    <HelpCTAOuter>
      <HelpPill />
    </HelpCTAOuter>
  );
};

const HelpPill: React.FC<{}> = () => {
  return (
    <HelpCTAInner
      onClick={() => {
        // eslint-disable-next-line wandb/no-unprefixed-urls
        window.open(HELP_LINK, '_blank');
      }}>
      <IconHelpAlt />
      <LE.Block>Get help or share feedback</LE.Block>
    </HelpCTAInner>
  );
};
