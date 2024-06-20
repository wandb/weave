import {makeTrackEvent} from './makeTrackEvent';

export const objectViewed = makeTrackEvent<
  {
    objectType: string;
    objectId: string;
    userId: string;
    organizationName: string;
    entityName: string;
  },
  {
    _description: `User viewed the detail view of an object`;
    _location: '/objects/:itemName/versions/:version?/:refExtra*';
    _motivation: 'Used for object views';
    objectType: {
      description: 'Type of object viewed';
      exampleValues: ['my-org', 'my-user'];
    };
    objectId: {
      description: 'ID of object viewed';
      exampleValues: [
        'm7yVOqoSLhTuoN1E6uMKSq4tgCc5il0hxYqMrA4UsEY',
        'm7yVOqoSLhTuoN1E6uMKSq4tgCc5il0hxYqMrA4UsEY'
      ];
    };
    userId: {
      description: 'ID of user viewing object';
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
>('Weave object viewed');

export const traceViewed = makeTrackEvent<
  {
    traceId: string;
    userId: string;
    organizationName: string;
    entityName: string;
  },
  {
    _description: `User viewed the detail view of a trace`;
    _location: '/calls/:itemName';
    _motivation: 'Used for object views';
    traceId: {
      description: 'ID of trace viewed';
      exampleValues: [
        'bb5621fd-91bc-42af-b017-1a34e3250330',
        'b2136295-edc5-4778-9304-0fa36c9541a4'
      ];
    };
    userId: {
      description: 'ID of user viewing trace';
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
>('Weave trace viewed');

export const evaluationViewed = makeTrackEvent<
  {
    traceId: string;
    userId: string;
    organizationName: string;
    entityName: string;
  },
  {
    _description: `User viewed the detail view of an evaluation`;
    _location: '/calls/:itemName';
    _motivation: 'Used for object views';
    traceId: {
      description: 'ID of evaluation viewed';
      exampleValues: [
        'bb5621fd-91bc-42af-b017-1a34e3250330',
        'b2136295-edc5-4778-9304-0fa36c9541a4'
      ];
    };
    userId: {
      description: 'ID of user viewing evaluation';
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
>('Weave evaluation viewed');
