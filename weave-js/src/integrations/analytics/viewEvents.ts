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
      exampleValues: ['123', '456'];
    };
    userId: {
      description: 'ID of user viewing object';
      exampleValues: ['123', '456'];
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
      exampleValues: ['123', '456'];
    };
    userId: {
      description: 'ID of user viewing object';
      exampleValues: ['123', '456'];
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
      exampleValues: ['123', '456'];
    };
    userId: {
      description: 'ID of user viewing object';
      exampleValues: ['123', '456'];
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
