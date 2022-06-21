import React from 'react';
import * as CGReact from '@wandb/common/cgreact';
import * as Op from '@wandb/cg/browser/ops';
import {Panel2Loader} from '../PanelComp';
import {Tag} from '@wandb/common/components/Tags';
import {colorIndex} from '@wandb/common/components/Artifact';
import * as Panel2 from '../panel';
import {inputType} from './common';
import styled from 'styled-components';

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

const PanelArtifactVersionAliases: React.FC<PanelArtifactVersionAliasesProps> =
  props => {
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
                colorIndex: colorIndex({alias: artifactVersionAlias}),
              }}
            />
          );
        })}
      </Wrapper>
    );
  };

export default PanelArtifactVersionAliases;
