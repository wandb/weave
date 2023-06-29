import {Node, voidNode} from '@wandb/weave/core';
import moment from 'moment';
import React, {FC, memo, useCallback, useMemo, useState} from 'react';
import getConfig from '../../../config';

import styled from 'styled-components';
import {WBButton} from '../../../common/components/elements/WBButtonNew';
import {useWeaveContext} from '../../../context';
import {ChildPanelFullConfig} from '../../Panel2/ChildPanel';
import {
  IconAddNew as IconAddNewUnstyled,
  IconCopy,
  IconDashboardBlackboard,
  IconInfo,
  IconLaptopLocalComputer,
  IconOverflowHorizontal,
  IconTable,
  IconUserProfilePersonal,
  IconUsersTeam,
  IconWandb,
  IconWeaveLogo,
} from '../../Panel2/Icons';
import {useNewPanelFromRootQueryCallback} from '../../Panel2/PanelRootBrowser/util';
import {useConfig} from '../../Panel2/panel';
import {Divider, Dropdown, Input, Popup} from 'semantic-ui-react';
import * as query from './query';

const CenterTable = styled.table`
  width: 100%;
  border: none;
  border-collapse: collapse;

  td:first-child {
    padding-left: 12px;
  }

  tr {
    border-top: 1px solid #dadee3;
    border-bottom: 1px solid #dadee3;
    color: #2b3038;
  }

  thead {
    tr {
      text-transform: uppercase;
      height: 48px;
      background-color: #f5f6f7;
      color: #8e949e;
      font-size: 14px;
      font-weight: 600;
    }
  }
  tbody {
    font-size: 16px;
    tr {
      height: 64px;

      &:hover {
        cursor: pointer;
        background-color: #f8f9fa;
      }
    }
    tr > td:first-child {
      font-weight: 600;
    }
  }
`;

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

const CenterTableActionCellAction = styled(HBlock)`
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

const CenterTableActionCellContents = styled(VStack)`
  align-items: center;
  justify-content: center;
`;

const CenterTableActionCellIcon = styled(VStack)`
  align-items: center;
  justify-content: center;
  height: 32px;
  width: 32px;
  border-radius: 4px;
  &:hover {
    background-color: #a9edf252;
    color: #038194;
  }
`;

const CenterSpaceTableSpace = styled(Space)`
  overflow: auto;
`;

const CenterSpaceControls = styled(HBlock)`
  gap: 8px;
`;

const CenterSpaceTitle = styled(HBlock)`
  font-size: 24px;
  font-weight: 600;
  padding: 12px 8px;
`;

const CenterSpaceHeader = styled(VBlock)`
  padding: 12px 16px;
  gap: 12px;
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

  const [activeBrowserRoot, setActiveBrowserRoot] = useState<{
    browserType: 'recent' | 'wandb' | 'drafts';
    rootId: string;
  }>({
    browserType: 'recent',
    rootId: 'boards',
  });

  const userEntities = query.useUserEntities();
  const userName = query.useUserName();

  const recentSection = useMemo(() => {
    return [
      {
        title: `Recent`,
        items: [
          {
            icon: IconDashboardBlackboard,
            label: `Boards`,
            active:
              activeBrowserRoot.browserType === 'recent' &&
              activeBrowserRoot.rootId === 'boards',
            onClick: () => {
              setActiveBrowserRoot({
                browserType: 'recent',
                rootId: 'boards',
              });
            },
          },
          {
            icon: IconTable,
            label: `Tables`,
            active:
              activeBrowserRoot.browserType === 'recent' &&
              activeBrowserRoot.rootId === 'tables',
            onClick: () => {
              setActiveBrowserRoot({
                browserType: 'recent',
                rootId: 'tables',
              });
            },
          },
        ],
      },
    ];
  }, [activeBrowserRoot.browserType, activeBrowserRoot.rootId]);

  const wandbSection = useMemo(() => {
    return userEntities.result.length === 0
      ? ([] as any)
      : [
          {
            title: `Weights & Biases`,
            items: userEntities.result
              .sort((a, b) => {
                if (a === userName.result) {
                  return -1;
                }
                if (b === userName.result) {
                  return 1;
                }
                if (a < b) {
                  return -1;
                }
                if (a > b) {
                  return 1;
                }
                return 0;
              })
              .map((entity, i) => ({
                icon:
                  entity === userName.result
                    ? IconUserProfilePersonal
                    : IconUsersTeam,
                label: entity,
                active:
                  activeBrowserRoot.browserType === 'wandb' &&
                  activeBrowserRoot.rootId === entity,
                onClick: () => {
                  setActiveBrowserRoot({
                    browserType: 'wandb',
                    rootId: entity,
                  });
                },
              })),
          },
        ];
  }, [
    activeBrowserRoot.browserType,
    activeBrowserRoot.rootId,
    userEntities.result,
    userName.result,
  ]);

  const draftsSection = useMemo(() => {
    return [
      {
        title: `Drafts`,
        items: [
          {
            icon: IconWandb,
            label: `W&B hosted workspace`,
            active:
              activeBrowserRoot.browserType === 'drafts' &&
              activeBrowserRoot.rootId === 'wb_hosted',
            onClick: () => {
              setActiveBrowserRoot({
                browserType: 'wandb',
                rootId: 'wb_hosted',
              });
            },
          },
          {
            icon: IconLaptopLocalComputer,
            label: `On this machine`,
            active:
              activeBrowserRoot.browserType === 'drafts' &&
              activeBrowserRoot.rootId === 'local',
            onClick: () => {
              setActiveBrowserRoot({
                browserType: 'wandb',
                rootId: 'local',
              });
            },
          },
        ],
      },
    ];
  }, [activeBrowserRoot.browserType, activeBrowserRoot.rootId]);

  const navSections = useMemo(() => {
    return [...recentSection, ...wandbSection, ...draftsSection];
  }, [draftsSection, recentSection, wandbSection]);

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
        <LeftNav sections={navSections} />
        {/* Center Content */}
        <CenterEntityBrowser entityName="timssweeney" />
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

const CenterEntityBrowser: React.FC<{
  entityName: string;
}> = props => {
  const browserTitle = props.entityName;

  console.log(query.useProjectsForEntityWithWeaveObject(props.entityName));

  const onSearch = useCallback(() => {}, []);

  const browserFilters = [
    {
      placeholder: 'All entities',
      options: [
        {key: 1, text: 'Choice 1', value: 1},
        {key: 2, text: 'Choice 2', value: 2},
        {key: 3, text: 'Choice 3', value: 3},
      ],
      onChange: () => {},
    },
    {
      placeholder: 'All projects',
      options: [
        {key: 1, text: 'Choice 1', value: 1},
        {key: 2, text: 'Choice 2', value: 2},
        {key: 3, text: 'Choice 3', value: 3},
      ],
      onChange: () => {},
    },
  ];

  const browserData: Array<CenterBrowserDataType> = [
    {
      _id: 0,
      Board: 'Board 1',
      Entity: 'timssweeney',
      Project: 'weave',
      'Last modified': '2 days ago',
    },
    {
      _id: 1,
      Board: 'Board 2',
      Entity: 'timssweeney',
      Project: 'weave',
      'Last modified': 'June 21, 2023',
    },
  ];
  const browserActions: Array<CenterBrowserActionType> = [
    [
      {
        icon: IconInfo,
        label: 'Object details',
        onClick: (row: CenterBrowserDataType, index: number) => {
          console.log('DETAILS', row, index);
        },
      },
      {
        icon: IconAddNew,
        label: 'Seed new board',
        onClick: (row: CenterBrowserDataType, index: number) => {
          console.log('SEED', row, index);
        },
      },
    ],
    [
      {
        icon: IconCopy,
        label: 'Copy Weave expression',
        onClick: (row: CenterBrowserDataType, index: number) => {
          console.log('COPY', row, index);
        },
      },
    ],
  ];
  return (
    <CenterBrowser
      data={browserData}
      actions={browserActions}
      title={browserTitle}
      onSearch={onSearch}
      filters={browserFilters}
    />
  );
};

const LeftNav: React.FC<{
  sections: Array<LeftNavSectionProps>;
}> = props => {
  return (
    <VBlock
      style={{
        width: '300px',
        paddingTop: '0px', // Cecile's design has spacing here, but i kind of like it without
        overflowY: 'auto',
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
          position: 'sticky',
          backgroundColor: '#fff',
          top: 0,
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

type CenterBrowserDataType = {
  _id: string | number;
  [key: string]: string | number;
};

type CenterBrowserActionType = Array<{
  icon: React.FC;
  label: string;
  onClick: (row: CenterBrowserDataType, index: number) => void;
}>;

type CenterBrowserProps = {
  title: string;
  data: Array<CenterBrowserDataType>;
  // TODO: Actions might be a callback that returns an array of actions for a row
  actions?: Array<CenterBrowserActionType>;
  onSearch?: (query: string) => void;
  filters?: Array<{
    placeholder: string;
    options: Array<{
      key: string | number;
      text: string;
      value: string | number;
    }>;
    onChange: (value: string) => void;
  }>;
};

const CenterBrowser: React.FC<CenterBrowserProps> = props => {
  const showControls = props.onSearch || (props.filters?.length ?? 0) > 0;
  const allActions = (props.actions ?? []).flatMap(a => a);
  const primaryAction = allActions.length > 0 ? allActions[0] : undefined;
  const columns = Object.keys(props.data[0] ?? {}).filter(
    k => !k.startsWith('_')
  );
  const hasActions = allActions.length > 0;
  return (
    <CenterSpace>
      <CenterSpaceHeader>
        <CenterSpaceTitle>{props.title}</CenterSpaceTitle>
        {showControls && (
          <CenterSpaceControls>
            {props.onSearch && (
              <Input
                style={{
                  width: '100%',
                }}
                icon="search"
                iconPosition="left"
                placeholder="Search"
                onChange={e => {
                  props.onSearch?.(e.target.value);
                }}
              />
            )}
            {props.filters?.map((filter, i) => (
              <Dropdown
                key={i}
                style={{
                  boxShadow: 'none',
                }}
                selection
                clearable
                placeholder={filter.placeholder}
                options={filter.options}
                onChange={(e, data) => {
                  filter.onChange(data.value as string);
                }}
              />
            ))}
          </CenterSpaceControls>
        )}
      </CenterSpaceHeader>
      <CenterSpaceTableSpace>
        <CenterTable>
          <thead>
            <tr>
              {columns.map((c, i) => (
                <td key={c}>{c}</td>
              ))}
              {hasActions && (
                <td
                  style={{
                    width: '64px',
                  }}></td>
              )}
            </tr>
          </thead>
          <tbody>
            {props.data.map((row, i) => (
              <tr key={row._id} onClick={() => primaryAction?.onClick(row, i)}>
                {columns.map((c, i) => (
                  <td key={c}>{row[c]}</td>
                ))}
                {hasActions && (
                  <td>
                    <CenterTableActionCellContents>
                      <Popup
                        style={{
                          padding: '6px 6px',
                        }}
                        content={
                          <VStack
                            onClick={e => {
                              e.stopPropagation();
                            }}>
                            {props.actions?.flatMap((action, i) => {
                              const actions = action.map((a, j) => (
                                <CenterTableActionCellAction
                                  key={'' + i + '_' + j}
                                  onClick={e => {
                                    e.stopPropagation();
                                    a.onClick(row, i);
                                  }}>
                                  <a.icon />
                                  {a.label}
                                </CenterTableActionCellAction>
                              ));
                              if (i < props.actions!.length - 1) {
                                actions.push(
                                  <Divider
                                    key={'d' + i}
                                    style={{margin: '6px 0px'}}
                                  />
                                );
                              }
                              return actions;
                            })}
                          </VStack>
                        }
                        basic
                        on="click"
                        trigger={
                          <CenterTableActionCellIcon
                            onClick={e => {
                              e.stopPropagation();
                            }}>
                            <IconOverflowHorizontal />
                          </CenterTableActionCellIcon>
                        }
                      />
                    </CenterTableActionCellContents>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </CenterTable>
      </CenterSpaceTableSpace>
    </CenterSpace>
  );
};

export const Home = memo(HomeComp);

const TopBar = styled.div`
  height: 64px;
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
