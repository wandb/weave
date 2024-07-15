import {makeTrackEvent} from './makeTrackEvent';

export const deleteClicked = makeTrackEvent<
  {
    callIds: string[];
    numCalls: number;
    userId: string;
    organizationName: string;
    entityName: string;
  },
  {
    _description: `User clicked the delete button`;
    _location: '';
    _motivation: 'Used for tracking deletion';
    callIds: {
      description: 'IDs of calls deleted';
      exampleValues: [
        [
          'bb5621fd-91bc-42af-b017-1a34e3250330',
          'b2136295-edc5-4778-9304-0fa36c9541a4'
        ],
        ['bb5621fd-91bc-42af-b017-1a34e3250330']
      ];
    };
    numCalls: {
      description: 'Number of calls deleted';
      exampleValues: [2, 1];
    };
    userId: {
      description: 'ID of user deleting';
      exampleValues: ['VXNlcjo0NTM4MTM='];
    };
    organizationName: {
      description: 'Name of organization';
      exampleValues: ['my-org'];
    };
    entityName: {
      description: 'Name of entity';
      exampleValues: ['my-entity'];
    };
  }
>('Weave delete clicked');
