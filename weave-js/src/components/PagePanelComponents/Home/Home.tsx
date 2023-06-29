import {Node, voidNode} from '@wandb/weave/core';
import moment from 'moment';
import React, {FC, memo, useCallback, useState} from 'react';
import getConfig from '../../../config';

import styled from 'styled-components';
import {WBButton} from '../../../common/components/elements/WBButtonNew';
import {useWeaveContext} from '../../../context';
import {ChildPanelFullConfig} from '../../Panel2/ChildPanel';
import {
  IconAddNew as IconAddNewUnstyled,
  IconDashboardBlackboard,
  IconLaptopLocalComputer,
  IconTable,
  IconUsersTeam,
  IconWeaveLogo,
} from '../../Panel2/Icons';
import {useNewPanelFromRootQueryCallback} from '../../Panel2/PanelRootBrowser/util';
import {useConfig} from '../../Panel2/panel';
import {Dropdown, Input} from 'semantic-ui-react';

const STYLE_DEBUG = false;

const debug_style = `
  ${
    STYLE_DEBUG
      ? 'background-color: rgba(0,0,0,0.1); border: 1px solid red;'
      : ''
  }
`;

const VStack = styled.div`
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  ${debug_style}
`;

const HStack = styled.div`
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: row;
  ${debug_style}
`;

const Space = styled.div`
  height: 100%;
  width: 100%;
  overflow: hidden;
  flex: 1 1 auto;
  ${debug_style}
`;

const Block = styled.div`
  flex: 0 0 auto;
  ${debug_style}
`;

const VSpace = styled.div`
  height: 100%;
  width: 100%;
  overflow: hidden;
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  ${debug_style}
`;

const HSpace = styled.div`
  height: 100%;
  width: 100%;
  overflow: hidden;
  flex: 1 1 auto;
  display: flex;
  flex-direction: row;
  ${debug_style}
`;

const VBlock = styled.div`
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  ${debug_style}
`;

const HBlock = styled.div`
  flex: 0 0 auto;
  display: flex;
  flex-direction: row;
  ${debug_style}
`;

const LeftNavItemBlock = styled(HBlock)`
  margin: 0px 12px;
  padding: 0px 12px;
  border-radius: 4px;
  height: 36px;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  cursor: pointer;
  &:hover {
    background-color: #f5f6f7;
  }
`;

const CenterSpace = styled(VSpace)`
  border: 1px solid #dadee3;
  box-shadow: 0px 8px 16px 0px #0e10140a;
  border-top-right-radius: 12px;
  border-top-left-radius: 12px;
  margin-right: 12px;
`;

type HomeProps = {
  updateConfig: (newConfig: ChildPanelFullConfig) => void;
  inJupyter: boolean;
};

const HomeComp: FC<HomeProps> = props => {
  const now = moment().format('YY_MM_DD_hh_mm_ss');
  const inJupyter = props.inJupyter;
  const defaultName = now;
  const [newName] = useState('');
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
  const [activeItem, setActiveItem] = useState(0);
  const numRecent = 2;
  const numWandb = 2;
  return (
    <VStack>
      <Block>
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
      </Block>
      {/* Main Region */}
      <HSpace>
        {/* Left Bar */}
        <LeftNav
          sections={[
            {
              title: `Recent`,
              items: [
                {
                  icon: IconDashboardBlackboard,
                  label: `Boards`,
                  active: activeItem === 0,
                  onClick: () => {
                    setActiveItem(0);
                  },
                },
                {
                  icon: IconTable,
                  label: `Tables`,
                  active: activeItem === 1,
                  onClick: () => {
                    setActiveItem(1);
                  },
                },
              ],
            },
            {
              title: `Weights & Biases`,
              items: [
                {
                  icon: IconUsersTeam,
                  label: `wandb`,
                  active: activeItem === 0 + numRecent,
                  onClick: () => {
                    setActiveItem(0 + numRecent);
                  },
                },
                {
                  icon: IconUsersTeam,
                  label: `timssweeney`,
                  active: activeItem === 1 + numRecent,
                  onClick: () => {
                    setActiveItem(1 + numRecent);
                  },
                },
              ],
            },
            {
              title: `Local`,
              items: [
                {
                  icon: IconLaptopLocalComputer,
                  label: `On this machine`,
                  active: activeItem === 0 + numRecent + numWandb,
                  onClick: () => {
                    setActiveItem(0 + numRecent + numWandb);
                  },
                },
              ],
            },
          ]}
        />
        {/* Center Content */}
        <CenterSpace>
          <VBlock
            style={{
              padding: '12px 16px',
              gap: '12px',
            }}>
            <HBlock
              style={{
                fontSize: '24px',
                fontWeight: 600,
                padding: '12px 8px',
              }}>
              Boards
            </HBlock>
            <HBlock
              style={{
                gap: '8px',
              }}>
              <Input
                style={{
                  width: '100%',
                }}
                icon="search"
                iconPosition="left"
                placeholder="Search"
              />
              <Dropdown
                style={{
                  boxShadow: 'none',
                }}
                placeholder="All entities"
                clearable
                options={[
                  {key: 1, text: 'Choice 1', value: 1},
                  {key: 2, text: 'Choice 2', value: 2},
                  {key: 3, text: 'Choice 3', value: 3},
                ]}
                selection
              />
              <Dropdown
                style={{
                  boxShadow: 'none',
                }}
                placeholder="All projects"
                clearable
                options={[
                  {key: 1, text: 'Choice 1', value: 1},
                  {key: 2, text: 'Choice 2', value: 2},
                  {key: 3, text: 'Choice 3', value: 3},
                ]}
                selection
              />
            </HBlock>
          </VBlock>
          <Space
            style={{
              borderTop: '1px solid #dadee3',
            }}>
            TABLE
          </Space>
        </CenterSpace>
        {/* Right Bar */}
        {/* <Block>
          <div
            style={{
              width: '300px',
            }}>
            c
          </div>
        </Block> */}
      </HSpace>
    </VStack>
  );
};

const LeftNav: React.FC<{
  sections: Array<LeftNavSectionProps>;
}> = props => {
  return (
    <VBlock
      style={{
        width: '300px',
        paddingTop: '24 px',
      }}>
      {props.sections.map((section, i) => (
        <LeftNavSection key={i} {...section} />
      ))}
    </VBlock>
  );
};

type LeftNavSectionProps = {
  title: string;
  items: Array<LeftNavItemProps>;
};

const LeftNavSection: React.FC<LeftNavSectionProps> = props => {
  return (
    <VBlock
      style={{
        marginBottom: '16px',
      }}>
      {/* Header */}
      <HBlock
        style={{
          textTransform: 'uppercase',
          padding: '10px 24px',
          fontSize: '14px',
        }}>
        {props.title}
      </HBlock>
      {/* Items */}
      <VBlock>
        {props.items.map((item, i) => (
          <LeftNavItem key={i} {...item} />
        ))}
      </VBlock>
    </VBlock>
  );
};

type LeftNavItemProps = {
  icon: React.FC;
  label: string;
  active?: boolean;
  onClick?: () => void;
};
const LeftNavItem: React.FC<LeftNavItemProps> = props => {
  return (
    <LeftNavItemBlock
      style={{
        backgroundColor: props.active ? '#A9EDF252' : '',
        color: props.active ? '#038194' : '',
        fontWeight: props.active ? 600 : '',
      }}
      onClick={props.onClick}>
      <props.icon />
      {props.label}
    </LeftNavItemBlock>
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

const BrowserSpace = styled.div`
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
