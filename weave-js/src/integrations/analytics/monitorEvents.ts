import {makeTrackEvent} from './makeTrackEvent';

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
