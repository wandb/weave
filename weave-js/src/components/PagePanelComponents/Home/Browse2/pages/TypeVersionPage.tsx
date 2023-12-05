import _ from 'lodash';
import React from 'react';

import {TypeLink, TypeVersionLink} from './common/Links';
import {
  ScrollableTabContent,
  SimpleKeyValueTable,
  SimplePageLayout,
} from './common/SimplePageLayout';
import {useWeaveflowORMContext} from './interface/wf/context';
import {HackyTypeTree, WFTypeVersion} from './interface/wf/types';
import {ObjectVersionsTable} from './ObjectVersionsPage';

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
          content: <div>TODO</div>,
        },
        {
          label: 'Consuming Ops',
          content: <div>TODO</div>,
        },
        {
          label: 'Producing Ops',
          content: <div>TODO</div>,
        },
        {
          label: 'DAG',
          content: <div>TODO</div>,
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
  const objectVersions = props.typeVersion.objectVersions();

  return <ObjectVersionsTable objectVersions={objectVersions} />;
};
