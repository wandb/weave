import {Node, voidNode} from '@wandb/weave/core';
import moment from 'moment';
import React, {FC, memo, useCallback, useState} from 'react';
import {Button, Input} from 'semantic-ui-react';
import getConfig from '../../config';

import {useWeaveContext} from '../../context';
import {ChildPanelFullConfig} from '../Panel2/ChildPanel';
import {PanelRootBrowser} from '../Panel2/PanelRootBrowser/PanelRootBrowser';
import {useNewPanelFromRootQueryCallback} from '../Panel2/PanelRootBrowser/util';
import {dummyProps, useConfig} from '../Panel2/panel';
import styled from 'styled-components';
import {IconWeaveLogo} from '../Panel2/Icons';

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
        <WeaveLogo />
        Weave
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
    // <div
    //   style={{
    //     width: '100%',
    //     height: '100%',
    //     display: 'flex',
    //     alignItems: 'center',
    //     justifyContent: 'center',
    //   }}>
    //   <div
    //     style={{
    //       width: '100%',
    //       height: '90%',
    //       display: 'flex',
    //       alignItems: 'center',
    //       justifyContent: 'center',
    //       // marginTop: 16,
    //       // marginBottom: 16,
    //     }}>
    //     <div
    //       style={{
    //         width: '90%',
    //         height: '100%',
    //         display: 'flex',
    //         alignItems: 'center',
    //         justifyContent: 'center',
    //         flexDirection: 'column',
    //         gap: 16,
    //       }}>
    //       <div
    //         style={{
    //           display: 'flex',
    //           flexDirection: 'row',
    //           // width: 400,
    //           padding: 16,
    //           border: '1px solid #eee',
    //           gap: 16,
    //           width: '100%',
    //         }}>
    //         <div
    //           style={{
    //             flexGrow: 1,
    //             width: '100%',
    //             display: 'flex',
    //             alignItems: 'center',
    //             gap: 8,
    //           }}>
    //           <div
    //             style={{width: '100%', display: 'flex', alignItems: 'center'}}
    //             onKeyUp={e => {
    //               if (e.key === 'Enter') {
    //                 newDashboard();
    //               }
    //             }}>
    //             <Input
    //               data-cy="new-dashboard-input"
    //               placeholder={defaultName}
    //               style={{flexGrow: 1}}
    //               value={newName}
    //               onChange={(e, {value}) => setNewName(value)}
    //             />
    //           </div>
    //           <div
    //             style={{
    //               display: 'flex',
    //               flex: 1,
    //               width: '100%',
    //             }}>
    //             <Button onClick={newDashboard}>New dashboard</Button>
    //           </div>
    //         </div>
    //       </div>
    //       <div
    //         style={{
    //           width: '100%',
    //           height: '100%',
    //           padding: 16,
    //           border: '1px solid #eee',
    //           display: 'flex',
    //           flexDirection: 'column',
    //           overflow: 'hidden',
    //         }}>
    //         {/* <div style={{marginBottom: 32}}>Your Weave Objects</div> */}
    //         <div style={{flexGrow: 1, overflow: 'auto'}}>
    //           <PanelRootBrowser
    //             input={voidNode() as any}
    //             updateInput={updateInput as any}
    //             isRoot={true}
    //             config={rootConfig}
    //             updateConfig={updateRootConfig}
    //             context={dummyProps.context}
    //             updateContext={dummyProps.updateContext}
    //           />
    //           {/* <DashboardList loadDashboard={loadDashboard} /> */}
    //         </div>
    //       </div>
    //     </div>
    //   </div>
    // </div>
  );
};

export const Home = memo(HomeComp);

const TopBar = styled.div`
  height: 48px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  font-size: 18px;
  font-weight: 600;
`;

const BrowserContainer = styled.div`
  height: calc(100% - 48px);
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 56px;
`;

const WeaveLogo = styled(IconWeaveLogo)`
  width: 32px;
  height: 32px;
  margin-right: 12px;
`;
