import * as globals from '@wandb/common/css/globals.styles';

import styled from 'styled-components';
import {WBIcon} from '@wandb/ui';

export const ControlBar = styled.div`
  height: 1.7em;
  border-top: 1px solid #ddd;
  background-color: #f8f8f8;
  display: flex;
  justify-content: space-betwee;
`;

export const ArrowIcon = styled(WBIcon)`
  cursor: pointer;
  height: 100%;
  padding: 4px 0px 0px 0px;
  :hover {
    color: ${globals.primary};
    background-color: #eee;
    border-radius: 2px;
  }
  flex: 0 0 auto;
`;
