import _ from 'lodash';
import React from 'react';

import {TypeLink, TypeVersionLink} from './common/Links';
import {
  ScrollableTabContent,
  SimpleKeyValueTable,
  SimplePageLayout,
} from './common/SimplePageLayout';
import {TypeVersionCategoryChip} from './common/TypeVersionCategoryChip';
import {UnderConstruction} from './common/UnderConstruction';
import {useWeaveflowORMContext} from './interface/wf/context';
import {HackyTypeTree, WFTypeVersion} from './interface/wf/types';
import {FilterableObjectVersionsTable} from './ObjectVersionsPage';
import {FilterableOpVersionsTable} from './OpVersionsPage';
import {FilterableTypeVersionsTable} from './TypeVersionsPage';

export const TypeVersionPage: React.FC<{
  entity: string;
  project: string;
  typeName: string;
  version: string;
}> = props => {
  const orm = useWeaveflowORMContext();
  const typeVersion = orm.projectConnection.typeVersion(
    props.typeName,
    props.version
  );
  return (
    <SimplePageLayout
      title={props.typeName + ' : ' + props.version}
      tabs={[
        {
          label: 'Overview',
          content: (
            <ScrollableTabContent>
              <SimpleKeyValueTable
                data={{
                  'Type Name': (
                    <TypeLink typeName={typeVersion.type().name()} />
                  ),
                  Category: (
                    <TypeVersionCategoryChip
                      typeCategory={typeVersion.typeCategory()}
                    />
                  ),
                  Version: typeVersion.version(),
                  'Property Types': (
                    <PropertyTypeTree
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
              return [key, <TypeLink typeName={value} />];
            }
            return [
              key,
              <PropertyTypeTree typeTree={value} skipType={false} />,
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
        paddingLeft: '1rem',
        margin: 0,
      }}>
      <li>
        <TypeVersionLink
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
  return (
    <FilterableObjectVersionsTable
      entity={props.typeVersion.entity()}
      project={props.typeVersion.project()}
      frozenFilter={{
        typeVersions: [
          props.typeVersion.type().name() + ':' + props.typeVersion.version(),
        ],
      }}
    />
  );
};

const TypeVersionConsumingOps: React.FC<{
  typeVersion: WFTypeVersion;
}> = props => {
  return (
    <FilterableOpVersionsTable
      entity={props.typeVersion.entity()}
      project={props.typeVersion.project()}
      frozenFilter={{
        consumesTypeVersions: [
          props.typeVersion.type().name() + ':' + props.typeVersion.version(),
        ],
      }}
    />
  );
};

const TypeVersionProducingOps: React.FC<{
  typeVersion: WFTypeVersion;
}> = props => {
  return (
    <FilterableOpVersionsTable
      entity={props.typeVersion.entity()}
      project={props.typeVersion.project()}
      frozenFilter={{
        producesTypeVersions: [
          props.typeVersion.type().name() + ':' + props.typeVersion.version(),
        ],
      }}
    />
  );
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
