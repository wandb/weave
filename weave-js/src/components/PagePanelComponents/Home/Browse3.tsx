import React, {FC, useEffect, useMemo} from 'react';
import {
  Switch,
  Route,
  Link as RouterLink,
  useParams,
  useHistory,
} from 'react-router-dom';

import {URL_BROWSE3} from '../../../urls';
import styled from 'styled-components';
import {
  IconDashboardBlackboard,
  IconStack,
  IconWeaveLogo,
} from '../../Panel2/Icons';
import {
  IconChartHorizontalBars,
  IconCheckmark,
  IconDocumentation,
  IconInfo,
  IconMagicWandStar,
  IconModel,
  IconNumber,
  IconSystem,
  IconTable,
  IconTextLanguage,
} from '../../Icon';
import {Dropdown} from 'semantic-ui-react';
import {useUserEntities} from './query';
import {useNodeValue} from '../../../react';
import {
  constFunction,
  constString,
  opDict,
  opEntityName,
  opEntityProjects,
  opIsNone,
  opMap,
  opProjectName,
  opRootAllProjects,
  opRootProject,
  opRootViewer,
  opUserEntities,
} from '../../../core';

const CustomHeaderNavContainer = styled.div`
  background-color: #191a1d;
  height: 60px;
  width: 100%;
  flex: 0 0 auto;
  display: flex;
  flex-direction: row;
  align-items: center;
  padding: 0px 20px;
`;

const Browse3Container = styled.div`
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background-color: #fafafa;
  display: flex;
  flex-direction: column;
`;

const NavBarSectionItemIcon = styled.div`
  flex: 0;
  display: flex;
  align-items: center;
`;

const NavBarSectionItemText = styled.div`
  flex: 1;
  display: flex;
  align-items: center;
`;

const NavBarSectionItem = styled.div<{disabled?: boolean}>`
  display: flex;
  flex-direction: row;
  height: 32px;
  border-radius: 4px;
  gap: 10px;
  padding: 0 10px;
  ${props =>
    props.disabled
      ? `
    color: #999;
  `
      : `
    &:hover {
        background-color: #ebebeb;
        cursor: pointer;
    }
  `}

  // A little transition to make the hover feel smoother
  transition: background-color 0.5s cubic-bezier(0.075, 0.82, 0.165, 1);
`;

const NavBarSectionItems = styled.div`
  display: flex;
  flex-direction: column;

  gap: 10px;
`;

const NavBarSectionHeaderText = styled.div`
  flex: 1;
  display: flex;
  align-items: center;
`;

const NavBarSectionHeader = styled.div`
  display: flex;
  flex-direction: row;
  height: 40px;

  padding: 0 10px;
  font-size: 20px;
`;

const NavBarSection = styled.div`
  display: flex;
  flex-direction: column;

  gap: 10px;
`;

const NavBarContainer = styled.div`
  width: 300px;
  height: 100%;
  overflow: auto;
  display: flex;
  flex-direction: column;
  background-color: #fff;
  border-right: 1px solid #e0e2e8;
  padding: 20px 10px;
  gap: 20px;
`;

const ContentContainer = styled.div`
  width: 100%;
  height: 100%;
  flex: 1;
  overflow: hidden;
`;

const Browse3RouterContainer = styled.div`
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: row;
  overflow: hidden;
`;

type SectionType = {
  key?: string;
  header: {
    title: React.ReactNode;
  };
  items: Array<{
    key?: string;
    preIcon: React.ReactNode;
    text: React.ReactNode;
    postIcon: React.ReactNode;
    disabled?: boolean;
    onClick?: () => void;
  }>;
};

const WBLikeNavbar: React.FC<{
  beforeSectionsChildren: React.ReactNode;
  sections: Array<SectionType>;
}> = props => {
  return (
    <NavBarContainer>
      {props.beforeSectionsChildren}
      {props.sections.map((section, sectionNdx) => {
        return (
          <NavBarSection key={section.key ?? sectionNdx}>
            <NavBarSectionHeader>
              <NavBarSectionHeaderText>
                {section.header.title}
              </NavBarSectionHeaderText>
            </NavBarSectionHeader>
            <NavBarSectionItems>
              {section.items.map((item, itemNdx) => {
                return (
                  <NavBarSectionItem
                    key={item.key ?? itemNdx}
                    disabled={item.disabled}
                    onClick={item.onClick}>
                    <NavBarSectionItemIcon>
                      {item.preIcon}
                    </NavBarSectionItemIcon>
                    <NavBarSectionItemText>{item.text}</NavBarSectionItemText>
                    <NavBarSectionItemIcon>
                      {item.postIcon}
                    </NavBarSectionItemIcon>
                  </NavBarSectionItem>
                );
              })}
            </NavBarSectionItems>
          </NavBarSection>
        );
      })}
    </NavBarContainer>
  );
};

const useWBNavbarSections = (): Array<SectionType> => {
  const history = useHistory();
  const selectedProject = useSelectedProject();
  return useMemo(() => {
    return [
      {
        key: 'types',
        header: {
          title: 'Types',
        },
        items: [
          {
            preIcon: <IconTable />,
            text: 'Dataset',
            onClick: () => {
              history.push({
                pathname: '/' + selectedProject + '/type/dataset',
              });
            },
          },
          {
            preIcon: <IconModel />,
            text: 'Model',
          },
          {
            preIcon: null,
            text: 'See All',
          },
        ],
      },
      {
        key: 'operations',
        header: {
          title: 'Operations',
        },
        items: [
          {
            preIcon: <IconStack />,
            text: 'Train',
          },
          {
            preIcon: <IconMagicWandStar />,
            text: 'Predict',
          },
          {
            preIcon: <IconNumber />,
            text: 'Score',
          },
          {
            preIcon: <IconCheckmark />,
            text: 'Evaluate',
          },
          {
            preIcon: <IconDocumentation />,
            text: 'Tune',
          },
          {
            preIcon: null,
            text: 'See All',
          },
        ],
      },
      {
        key: 'tools',
        header: {
          title: 'Tools',
        },
        items: [
          {
            preIcon: <IconDashboardBlackboard />,
            text: 'Board Designer',
          },
          {
            preIcon: <IconChartHorizontalBars />,
            text: 'Trace Debugger',
          },
          {
            preIcon: <IconTextLanguage />,
            text: 'Chat Playground',
            postIcon: <IconInfo />,
            disabled: true,
          },
          {
            preIcon: <IconStack />,
            text: 'Data Studio',
            postIcon: <IconInfo />,
            disabled: true,
          },
          {
            preIcon: <IconSystem />,
            text: 'Model Deployments',
            postIcon: <IconInfo />,
            disabled: true,
          },
        ],
      },
    ] as Array<SectionType>;
  }, [history, selectedProject]);
};

const useProjectOptions = () => {
  const projectNodeValue = useNodeValue(
    opMap({
      arr: opUserEntities({user: opRootViewer({})}),
      mapFn: constFunction({row: 'entity'}, ({row}) => {
        return opDict({
          entityName: opEntityName({entity: row}),
          projectNames: opProjectName({
            project: opEntityProjects({
              entity: row,
            }),
          }),
        } as any);
      }),
    })
  );

  const projects: Array<string> = useMemo(() => {
    return (
      projectNodeValue.result?.flatMap(
        ({
          entityName,
          projectNames,
        }: {
          entityName: string;
          projectNames: Array<string>;
        }) => {
          return projectNames.map(projectName => {
            return `${entityName}/${projectName}`;
          });
        }
      ) ?? []
    );
  }, [projectNodeValue.result]);

  return useMemo(() => {
    return projects.map(project => {
      return {
        key: project,
        text: project,
        value: project,
      };
    });
  }, [projects]);
};

const useProjectRedirectEffect = () => {
  const projectOptions = useProjectOptions();
  const params = useParams<ParamType>();
  const projectIsSelected =
    params.entityName != null && params.projectName != null;
  const history = useHistory();
  const projectMissingNodeValue = useNodeValue(
    opIsNone({
      val: opRootProject({
        entityName: constString(params.entityName ?? ''),
        projectName: constString(params.projectName ?? ''),
      }),
    })
  );
  useEffect(() => {
    if (projectOptions.length > 0) {
      const defaultPath = '/' + projectOptions[0].value;
      if (!projectIsSelected || projectMissingNodeValue.result === true) {
        history.push({
          pathname: defaultPath,
        });
      }
    }
  }, [
    history,
    projectIsSelected,
    projectMissingNodeValue.result,
    projectOptions,
  ]);
};

const useSelectedProject = () => {
  const params = useParams<ParamType>();
  return useMemo(() => {
    const entityName = params.entityName;
    const projectName = params.projectName;
    if (entityName != null && projectName != null) {
      return `${entityName}/${projectName}`;
    }
    return '';
  }, [params.entityName, params.projectName]);
};

type ParamType = {
  entityName?: string;
  projectName?: string;
};

const Browse3RouteAwareNavbar: React.FC = props => {
  const history = useHistory();
  const sections = useWBNavbarSections();
  const projectOptions = useProjectOptions();
  const selectedProject = useSelectedProject();
  useProjectRedirectEffect();

  return (
    <WBLikeNavbar
      beforeSectionsChildren={
        <div
          style={{
            padding: '0px 10px',
          }}>
          <Dropdown
            text={selectedProject}
            icon="folder"
            floating
            labeled
            search
            button
            className="icon"
            style={{
              width: '100%',
            }}
            options={projectOptions}
            onChange={(e, {value}) => {
              history.push({
                pathname: '/' + value,
              });
            }}
          />
        </div>
      }
      sections={sections}
    />
  );
};

export const Browse3Router: FC = props => {
  return (
    <Browse3RouterContainer>
      <Switch>
        <Route path={'/:entityName?/:projectName?/'}>
          <Browse3RouteAwareNavbar />
          <ContentContainer></ContentContainer>
        </Route>
      </Switch>
    </Browse3RouterContainer>
  );
};

const CustomHeaderNav: FC = props => {
  return (
    <CustomHeaderNavContainer>
      <IconWeaveLogo
        style={{
          height: '40px',
          width: '40px',
        }}
      />
    </CustomHeaderNavContainer>
  );
};

export const Browse3: FC = props => {
  // const route = useRoute();
  return (
    <Browse3Container>
      <CustomHeaderNav />
      <Browse3Router />
    </Browse3Container>
  );
};
