import {Node, voidNode} from '@wandb/weave/core';
import moment from 'moment';
import React, {FC, memo, useCallback, useState} from 'react';
import getConfig from '../../config';

import styled from 'styled-components';
import {WBButton} from '../../common/components/elements/WBButtonNew';
import {useWeaveContext} from '../../context';
import {ChildPanelFullConfig} from '../Panel2/ChildPanel';
import {IconAddNew as IconAddNewUnstyled, IconWeaveLogo} from '../Panel2/Icons';
import {PanelRootBrowser} from '../Panel2/PanelRootBrowser/PanelRootBrowser';
import {useNewPanelFromRootQueryCallback} from '../Panel2/PanelRootBrowser/util';
import {dummyProps, useConfig} from '../Panel2/panel';

type HomeProps = {
  updateConfig: (newConfig: ChildPanelFullConfig) => void;
  inJupyter: boolean;
};

const HomeComp: FC<HomeProps> = props => {
  const now = moment().format('YY_MM_DD_hh_mm_ss');
  const inJupyter = props.inJupyter;
  const defaultName = now;
  const [newName, setNewName] = useState('');
  const weave = useWeaveContext();
  const name = 'dashboard-' + (newName === '' ? defaultName : newName);
  const makeNewDashboard = useNewPanelFromRootQueryCallback();
  const {urlPrefixed} = getConfig();
  const newDashboard = useCallback(() => {
    makeNewDashboard(name, voidNode(), true, newDashExpr => {
      if (inJupyter) {
        const expStr = weave
          .expToString(newDashExpr)
          .replace(/\n+/g, '')
          .replace(/\s+/g, '');
        window.open(
          urlPrefixed(`?exp=${encodeURIComponent(expStr)}`),
          '_blank'
        );
      } else {
        props.updateConfig({
          vars: {},
          input_node: newDashExpr,
          id: '',
          config: undefined,
        });
      }
    });
  }, [inJupyter, makeNewDashboard, name, props, urlPrefixed, weave]);
  const [rootConfig, updateRootConfig] = useConfig();
  const updateInput = useCallback(
    (newInput: Node) => {
      props.updateConfig({
        vars: {},
        input_node: newInput,
        id: '',
        config: undefined,
      });
    },
    [props]
  );
  return (
    <>
      <TopBar>
        <TopBarLeft>
          <WeaveLogo />
          Weave
        </TopBarLeft>
        <TopBarRight>
          <WBButton variant={`confirm`} onClick={newDashboard}>
            <IconAddNew />
            New board
          </WBButton>
        </TopBarRight>
      </TopBar>
      <BrowserContainer>
        <PanelRootBrowser
          input={voidNode() as any}
          updateInput={updateInput as any}
          isRoot={true}
          config={rootConfig}
          updateConfig={updateRootConfig}
          context={dummyProps.context}
          updateContext={dummyProps.updateContext}
        />
      </BrowserContainer>
    </>
  );
};

export const Home = memo(HomeComp);

const TopBar = styled.div`
  height: 48px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const TopBarLeft = styled.div`
  display: flex;
  align-items: center;
  font-size: 18px;
  font-weight: 600;
`;

const TopBarRight = styled.div`
  display: flex;
  align-items: center;
`;

const BrowserContainer = styled.div`
  height: calc(100% - 48px);
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 32px 56px;
`;

const WeaveLogo = styled(IconWeaveLogo)`
  width: 32px;
  height: 32px;
  margin-right: 12px;
`;

const IconAddNew = styled(IconAddNewUnstyled)`
  width: 18px;
  height: 18px;
  margin-right: 6px;
`;
