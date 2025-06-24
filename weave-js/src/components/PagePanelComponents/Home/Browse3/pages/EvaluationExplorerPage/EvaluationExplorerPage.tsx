import {Box} from '@mui/material';
import {MOON_50, MOON_200} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import {Select} from '@wandb/weave/components/Form/Select';
import {Icon, IconName} from '@wandb/weave/components/Icon';
import React, {useMemo} from 'react';

import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {
  EvaluationExplorerPageProvider,
  useEvaluationExplorerPageContext,
} from './context';
import {clientBound, hookify} from './hooks';
import {getLatestEvaluationRefs} from './query';

const HEADER_HEIGHT_PX = 44;
const BORDER_COLOR = MOON_200;
const SECONDARY_BACKGROUND_COLOR = MOON_50;

type EvaluationExplorerPageProps = {
  entity: string;
  project: string;
};

export const EvaluationExplorerPage = (props: EvaluationExplorerPageProps) => {
  return (
    <SimplePageLayoutWithHeader
      title="EvaluationExplorer"
      hideTabsIfSingle
      headerContent={null}
      tabs={[
        {
          label: 'main',
          content: (
            <EvaluationExplorerPageProvider>
              <EvaluationExplorerPageInner {...props} />
            </EvaluationExplorerPageProvider>
          ),
        },
      ]}
      headerExtra={null}
    />
  );
};

const EvaluationExplorerPageInner: React.FC<EvaluationExplorerPageProps> = ({
  entity,
  project,
}) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();
  console.log(config);
  return (
    <Row>
      <ConfigPanel entity={entity} project={project} />
      <Column style={{flex: 1}}>
        <Header>Results</Header>
      </Column>
    </Row>
  );
};

const ConfigPanel: React.FC<{entity: string; project: string}> = ({
  entity,
  project,
}) => {
  return (
    <Column
      style={{
        maxWidth: '500px',
        minWidth: '300px',
        borderRight: `1px solid ${BORDER_COLOR}`,
        backgroundColor: SECONDARY_BACKGROUND_COLOR,
      }}>
      <Header>
        <span>Configuration</span>
        <Button
          icon="settings-parameters"
          size="small"
          variant="secondary"
          onClick={() => {
            console.error('TODO: Implement me');
          }}
        />
      </Header>
      <Column style={{flex: 1, overflowY: 'auto'}}>
        <ConfigSection title="Evaluation" icon="baseline-alt">
          <EvaluationPicker entity={entity} project={project} />
          <Column
            style={{
              flex: 0,
              borderLeft: `1px solid ${BORDER_COLOR}`,
              marginTop: '16px',
            }}>
            <ConfigSection
              title="Dataset"
              icon="table"
              style={{
                paddingTop: '0px',
                paddingRight: '0px',
              }}>
              <Select
                options={[]}
                value={''}
                onChange={option => {
                  console.log(option);
                  console.error('TODO: Implement me');
                }}
              />
            </ConfigSection>
            <ConfigSection
              title="Scorers"
              icon="type-number-alt"
              style={{
                paddingBottom: '0px',
                paddingRight: '0px',
              }}>
              <Column style={{gap: '8px'}}>
                <Row style={{alignItems: 'center', gap: '8px'}}>
                  <Button
                    icon="copy"
                    variant="ghost"
                    onClick={() => {
                      console.error('TODO: Implement me');
                    }}
                  />
                  <div style={{flex: 1}}>
                    <Select
                      options={[]}
                      value={''}
                      onChange={option => {
                        console.log(option);
                        console.error('TODO: Implement me');
                      }}
                    />
                  </div>
                  <Button
                    icon="settings"
                    variant="ghost"
                    onClick={() => {
                      console.error('TODO: Implement me');
                    }}
                  />
                  <Button
                    icon="remove"
                    variant="ghost"
                    onClick={() => {
                      console.error('TODO: Implement me');
                    }}
                  />
                </Row>
                <Row>
                  <Button
                    icon="add-new"
                    variant="ghost"
                    onClick={() => {
                      console.error('TODO: Implement me');
                    }}
                  />
                </Row>
              </Column>
            </ConfigSection>
          </Column>
        </ConfigSection>
        <ConfigSection title="Models" icon="model">
          <Select
            options={[]}
            value={''}
            onChange={option => {
              console.log(option);
              console.error('TODO: Implement me');
            }}
          />
        </ConfigSection>
      </Column>
      <Footer>
        <Button
          variant="secondary"
          onClick={() => {
            console.error('TODO: Implement me');
          }}>
          Clear
        </Button>
        <Button
          icon="play"
          variant="primary"
          onClick={() => {
            console.error('TODO: Implement me');
          }}>
          Run eval
        </Button>
      </Footer>
    </Column>
  );
};

const ConfigSection: React.FC<{
  title: string;
  icon: IconName;
  style?: React.CSSProperties;
  children?: React.ReactNode;
}> = ({title, icon, style, children}) => {
  return (
    <Column style={{padding: '8px 16px 16px 16px', flex: 0, ...style}}>
      <Row
        style={{
          alignItems: 'center',
          flex: 0,
          fontWeight: 600,
          paddingBottom: '8px',
        }}>
        <Icon name={icon} />
        <span style={{marginLeft: '4px'}}>{title}</span>
      </Row>
      {children}
    </Column>
  );
};

// Shared components

const Header: React.FC<{children?: React.ReactNode}> = ({children}) => {
  return (
    <div
      style={{
        height: HEADER_HEIGHT_PX,
        borderBottom: `1px solid ${BORDER_COLOR}`,
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        fontWeight: 600,
        fontSize: '18px',
        justifyContent: 'space-between',
      }}>
      {children}
    </div>
  );
};

const Footer: React.FC<{children?: React.ReactNode}> = ({children}) => {
  return (
    <div
      style={{
        height: HEADER_HEIGHT_PX,
        borderTop: `1px solid ${BORDER_COLOR}`,
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        fontWeight: 600,
        fontSize: '18px',
        justifyContent: 'space-between',
      }}>
      {children}
    </div>
  );
};

//  Generic components for layout

const Row: React.FC<{
  style?: React.CSSProperties;
  children?: React.ReactNode;
}> = ({style, children}) => {
  return (
    <Box
      style={{
        display: 'flex',
        flexDirection: 'row',
        height: '100%',
        width: '100%',
        flex: 1,
        ...style,
      }}>
      {children}
    </Box>
  );
};

const Column: React.FC<{
  style?: React.CSSProperties;
  children?: React.ReactNode;
}> = ({style, children}) => {
  return (
    <Box
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        flex: 1,
        ...style,
      }}>
      {children}
    </Box>
  );
};

const LoadingSelect: typeof Select = props => {
  return <Select isDisabled placeholder="Loading..." {...props} />;
};

// Specialized Components

const EvaluationPicker: React.FC<{entity: string; project: string}> = ({
  entity,
  project,
}) => {
  const refsQuery = useLatestEvaluationRefs(entity, project);
  const newEvaluationOption = useMemo(() => {
    return {
      label: 'New Evaluation',
      value: 'new-evaluation',
    };
  }, []);
  const selectOptions = useMemo(() => {
    return [
      newEvaluationOption,
      ...(refsQuery.data?.map(ref => ({
        label: ref,
      })) ?? []),
    ];
  }, [refsQuery.data, newEvaluationOption]);
  const selectedValue = useMemo(() => {
    return selectOptions[0];
  }, [selectOptions]);

  if (refsQuery.loading) {
    return <LoadingSelect />;
  }

  return (
    <Select
      options={selectOptions}
      value={selectedValue}
      onChange={option => {
        console.log(option);
        console.error('TODO: Implement me');
      }}
    />
  );
};

const useLatestEvaluationRefs = clientBound(hookify(getLatestEvaluationRefs));
