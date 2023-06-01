import {Tag, TagType} from '@wandb/weave/common/components/Tags';
import * as Op from '@wandb/weave/core';
import React from 'react';
import styled from 'styled-components';

import * as CGReact from '../../../react';
import * as Panel2 from '../panel';
import {Panel2Loader} from '../PanelComp';
import {inputType} from './common';

const Wrapper = styled.div`
  width: 100%;
  height: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  margin: auto;
  text-align: center;
  wordbreak: normal;
  display: flex;
  flex-direction: row;
  align-content: space-around;
  justify-content: left;
  align-items: center;
  -ms-overflow-style: none; /* IE and Edge */
  scrollbar-width: none; /* Firefox */
  &::-webkit-scrollbar {
    display: none;
  }
`;

type PanelArtifactVersionAliasesProps = Panel2.PanelProps<typeof inputType>;

const PanelArtifactVersionAliases: React.FC<
  PanelArtifactVersionAliasesProps
> = props => {
  const nodeValueQuery = CGReact.useNodeValue(
    Op.opArtifactAliasAlias({artifactAlias: props.input as any})
  );
  if (nodeValueQuery.loading) {
    return <Panel2Loader />;
  }
  if (nodeValueQuery.result == null) {
    return <div>-</div>;
  }
  return (
    <Wrapper>
      {nodeValueQuery.result.map((artifactVersionAlias: string) => {
        return (
          <Tag
            key={artifactVersionAlias}
            tag={{
              name: artifactVersionAlias,
              colorIndex: TagType.ALIAS,
            }}
            noun="alias"
          />
        );
      })}
    </Wrapper>
  );
};

export default PanelArtifactVersionAliases;
