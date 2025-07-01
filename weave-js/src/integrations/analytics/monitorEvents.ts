import {makeTrackEvent} from './makeTrackEvent';

export const newMonitorClicked = makeTrackEvent<
  {
    entity: string;
    project: string;
  },
  {
    _description: `User clicked the new monitor button`;
    _location: '';
    _motivation: 'Used for tracking new monitor clicks';
    entity: {
      description: 'Entity of monitor';
      exampleValues: ['my-entity'];
    };
    project: {
      description: 'Project of monitor';
      exampleValues: ['my-project'];
    };
  }
>('Weave new monitor clicked');

export const newMonitorCreated = makeTrackEvent<
  {
    entity: string;
    project: string;
    monitorName: string;
  },
  {
    _description: `User clicked the new monitor button`;
    _location: '';
    _motivation: 'Used for tracking new monitor clicks';
    entity: {
      description: 'Entity of monitor';
      exampleValues: ['my-entity'];
    };
    project: {
      description: 'Project of monitor';
      exampleValues: ['my-project'];
    };
    monitorName: {
      description: 'Name of monitor';
      exampleValues: ['my-monitor'];
    };
  }
>('Weave new monitor created');

export const monitorGoToTableClicked = makeTrackEvent<
  {
    entity: string;
    project: string;
    monitorName: string;
  },
  {
    _description: `User clicked the go to table button`;
    _location: '';
    _motivation: 'Used for tracking go to table clicks';
    entity: {
      description: 'Entity of monitor';
      exampleValues: ['my-entity'];
    };
    project: {
      description: 'Project of monitor';
      exampleValues: ['my-project'];
    };
    monitorName: {
      description: 'Name of monitor';
      exampleValues: ['my-monitor'];
    };
  }
>('Weave monitor go to table clicked');
