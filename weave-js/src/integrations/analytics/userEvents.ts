import {makeTrackEvent} from './makeTrackEvent';

export const deleteClicked = makeTrackEvent<
  {
    callIds: string[];
    numCalls: number;
    userId: string;
    organizationName: string;
    username: string;
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
    username: {
      description: 'Username of user deleting';
      exampleValues: ['my-username'];
    };
  }
>('Weave delete clicked');

export const exportClicked = makeTrackEvent<
  {
    numRows: number;
    numColumns: number | null;
    type: string;
    latency: number;
    dataSize: number;
    numExpandedColumns: number;
    maxDepth: number;
    userId: string;
    organizationName: string;
    username: string;
  },
  {
    _description: `User clicked the export button`;
    _location: '';
    _motivation: 'Used for tracking export';
    numRows: {
      description: 'Number of rows exported';
      exampleValues: [1000, 500];
    };
    numColumns: {
      description: 'Number of columns exported';
      exampleValues: [10, 5, null];
    };
    type: {
      description: 'Type of export';
      exampleValues: ['csv', 'json', 'jsonl'];
    };
    latency: {
      description: 'Latency of export';
      exampleValues: [1000, 500];
    };
    dataSize: {
      description: 'Size of data exported';
      exampleValues: [1000, 500];
    };
    numExpandedColumns: {
      description: 'Number of columns passed for ref expansion';
      exampleValues: [10, 5];
    };
    maxDepth: {
      description: 'Max depth of ref expansion';
      exampleValues: [1, 2, 5];
    };
    userId: {
      description: 'ID of user exporting';
      exampleValues: ['VXNlcjo0NTM4MTM='];
    };
    organizationName: {
      description: 'Name of organization';
      exampleValues: ['my-org'];
    };
    username: {
      description: 'Username of user exporting';
      exampleValues: ['my-username'];
    };
  }
>('Weave export clicked');
