import {Button} from '@wandb/weave/components/Button';
import {Select} from '@wandb/weave/components/Form/Select';
import React from 'react';

import {Column} from './layout';
import {ConfigSection, Row} from './layout';

export const ModelsConfigSection: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  return (
    <ConfigSection title="Models" icon="model">
      <Column style={{gap: '8px'}}>
        <Row style={{alignItems: 'center', gap: '8px'}}>
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
            icon="copy"
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
  );
};
