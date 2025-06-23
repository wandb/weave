import {Box} from '@mui/material';
import {MOON_50, MOON_200} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import {Select} from '@wandb/weave/components/Form/Select';
import {Icon, IconName} from '@wandb/weave/components/Icon';
import React from 'react';

import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';

const HEADER_HEIGHT_PX = 44;
const BORDER_COLOR = MOON_200;
const SECONDARY_BACKGROUND_COLOR = MOON_50;

export type EvaluationExplorerPageProps = {
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
          content: <EvaluationExplorerPageInner {...props} />,
        },
      ]}
      headerExtra={null}
    />
  );
};

export const EvaluationExplorerPageInner: React.FC<
  EvaluationExplorerPageProps
> = ({entity, project}) => {
  return (
    <Row>
      <ConfigPanel />
      <Column style={{flex: 1}}>
        <Header>Results</Header>
      </Column>
    </Row>
  );
};

const ConfigPanel: React.FC = () => {
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
            console.error('Not yet implemented');
          }}
        />
      </Header>
      <Column style={{flex: 1, overflowY: 'auto'}}>
        <ConfigSection title="Evaluation" icon="baseline-alt">
          <Select
            options={[]}
            value={''}
            onChange={option => {
              console.log(option);
              console.error('Not yet implemented');
            }}
          />
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
                  console.error('Not yet implemented');
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
              <Select
                options={[]}
                value={''}
                onChange={option => {
                  console.log(option);
                  console.error('Not yet implemented');
                }}
              />
            </ConfigSection>
          </Column>
        </ConfigSection>
        <ConfigSection title="Models" icon="model">
          <Select
            options={[]}
            value={''}
            onChange={option => {
              console.log(option);
              console.error('Not yet implemented');
            }}
          />
        </ConfigSection>
      </Column>
      <Footer>
        <Button
          variant="secondary"
          onClick={() => {
            console.error('Not yet implemented');
          }}>
          Clear
        </Button>
        <Button
          icon="play"
          variant="primary"
          onClick={() => {
            console.error('Not yet implemented');
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
    <Column style={{padding: '16px', flex: 0, ...style}}>
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
