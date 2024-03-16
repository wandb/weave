import * as globals from '@wandb/weave/common/css/globals.styles';
import React from 'react';
import styled from 'styled-components';

import {UnderConstruction} from './common/UnderConstruction';

const WeaveRoot = styled.div`
  position: absolute;
  top: 64px;
  bottom: 0;
  left: 240px;
  right: 0;
  background-color: ${globals.WHITE};
  color: ${globals.TEXT_PRIMARY_COLOR};
`;
WeaveRoot.displayName = 'S.WeaveRoot';

export const BoardPage: React.FC<{
  entity: string;
  project: string;
  boardId: string;
  versionId?: string;
}> = props => {
  return (
    <UnderConstruction
      title="Board"
      message={<>This page will contain an editable board</>}
    />
  );
};
