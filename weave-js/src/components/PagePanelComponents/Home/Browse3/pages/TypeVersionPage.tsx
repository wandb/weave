import _ from 'lodash';
import React from 'react';

import {TypeLink, TypeVersionLink} from './common/Links';
import {CenteredAnimatedLoader} from './common/Loader';
import {
  ScrollableTabContent,
  SimpleKeyValueTable,
  SimplePageLayout,
} from './common/SimplePageLayout';
import {TypeVersionCategoryChip} from './common/TypeVersionCategoryChip';
import {UnderConstruction} from './common/UnderConstruction';
import {FilterableTypeVersionsTable} from './TypeVersionsPage';
import {useWeaveflowORMContext} from './wfInterface/context';
import {HackyTypeTree, WFTypeVersion} from './wfInterface/types';

export const TypeVersionPage: React.FC<{
  entity: string;
  project: string;
  typeName: string;
  version: string;
}> = props => {
  const orm = useWeaveflowORMContext(props.entity, props.project);
  const typeVersion = orm.projectConnection.typeVersion(
    props.typeName,
    props.version
  );
  if (typeVersion == null) {
    return <CenteredAnimatedLoader />;
  }
  return <TypeVersionPageInner typeVersion={typeVersion} />;
};
const TypeVersionPageInner: React.FC<{
  typeVersion: WFTypeVersion;
}> = ({typeVersion}) => {
  const typeName = typeVersion.type().name();
  const typeVersionHash = typeVersion.version();
  return (
    <SimplePageLayout
      title={typeName + ' : ' + typeVersionHash}
      tabs={[
        {
          label: 'Overview',
          content: (
            <ScrollableTabContent>
              <SimpleKeyValueTable
                data={{
                  'Type Name': (
                    <TypeLink
                      entityName={typeVersion.entity()}
                      projectName={typeVersion.project()}
                      typeName={typeVersion.type().name()}
                    />
                  ),
                  Category: (
                    <TypeVersionCategoryChip
                      typeCategory={typeVersion.typeCategory()}
                    />
                  ),
                  Version: typeVersion.version(),
                  'Property Types': (
                    <PropertyTypeTree
                      entityName={typeVersion.entity()}
                      projectName={typeVersion.project()}
                      typeTree={typeVersion.propertyTypeTree()}
                      skipType={true}
                    />
                  ),
                  Hierarchy: <TypeHierarchy typeVersion={typeVersion} />,
                }}
              />
            </ScrollableTabContent>
          ),
        },
        {
          label: 'Objects',
          content: <TypeVersionObjectVersions typeVersion={typeVersion} />,
        },
        {
          label: 'Child Types',
          content: <TypeVersionChildTypes typeVersion={typeVersion} />,
        },
        {
          label: 'Consuming Ops',
          content: <TypeVersionConsumingOps typeVersion={typeVersion} />,
        },
        {
          label: 'Producing Ops',
          content: <TypeVersionProducingOps typeVersion={typeVersion} />,
        },
        {
          label: 'DAG',
          content: (
            <UnderConstruction
              title="Structure DAG"
              message={
                <>
                  This page will show a "Structure" DAG of Types and Ops
                  centered at this particular type.
                </>
              }
            />
          ),
        },
      ]}
    />
  );
};

const PropertyTypeTree: React.FC<{
  entityName: string;
  projectName: string;
  typeTree: HackyTypeTree;
  skipType: boolean;
}> = props => {
  if (typeof props.typeTree === 'string') {
    return <>{props.typeTree}</>;
  }
  return (
    <SimpleKeyValueTable
      data={_.fromPairs(
        _.entries(props.typeTree)
          .filter(
            ([key, value]) =>
              !key.startsWith('_') &&
              value !== 'OpDef' &&
              (!props.skipType || key !== 'type')
          )
          .map(([key, value]) => {
            if (typeof value === 'string' && key === 'type') {
              return [
                key,
                <TypeLink
                  entityName={props.entityName}
                  projectName={props.projectName}
                  typeName={value}
                />,
              ];
            }
            return [
              key,
              <PropertyTypeTree
                entityName={props.entityName}
                projectName={props.projectName}
                typeTree={value}
                skipType={false}
              />,
            ];
          })
      )}
    />
  );
};

const TypeHierarchy: React.FC<{typeVersion: WFTypeVersion}> = props => {
  const parentType = props.typeVersion.parentTypeVersion();
  const inner = (
    <ul
      style={{
        paddingInlineStart: '22px',
        margin: 0,
      }}>
      <li>
        <TypeVersionLink
          entityName={props.typeVersion.entity()}
          projectName={props.typeVersion.project()}
          typeName={props.typeVersion.type().name()}
          version={props.typeVersion.version()}
        />
      </li>
      {props.children}
    </ul>
  );
  if (!parentType) {
    return inner;
  } else {
    return <TypeHierarchy typeVersion={parentType}> {inner}</TypeHierarchy>;
  }
};

const TypeVersionObjectVersions: React.FC<{
  typeVersion: WFTypeVersion;
}> = props => {
  return <>Not Implemented</>;
};

const TypeVersionConsumingOps: React.FC<{
  typeVersion: WFTypeVersion;
}> = props => {
  return <>Not Implemented</>;
};

const TypeVersionProducingOps: React.FC<{
  typeVersion: WFTypeVersion;
}> = props => {
  return <>Not Implemented</>;
};

const TypeVersionChildTypes: React.FC<{
  typeVersion: WFTypeVersion;
}> = props => {
  return (
    <FilterableTypeVersionsTable
      entity={props.typeVersion.entity()}
      project={props.typeVersion.project()}
      frozenFilter={{
        parentType:
          props.typeVersion.type().name() + ':' + props.typeVersion.version(),
      }}
    />
  );
};
