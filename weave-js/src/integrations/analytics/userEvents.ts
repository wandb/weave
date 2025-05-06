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

export const callTreeCellClicked = makeTrackEvent<
  {
    callId: string;
    entity: string;
    project: string;
    traceId: string;
    path: string;
    isParentRow: boolean;
    hierarchyDepth: number;
  },
  {
    _description: `User clicked a call tree cell`;
    _location: '';
    _motivation: 'Used for tracking call tree cell clicks';
    callId: {
      description: 'ID of call';
      exampleValues: ['bb5621fd-91bc-42af-b017-1a34e3250330'];
    };
    entity: {
      description: 'Entity of call';
      exampleValues: ['my-entity'];
    };
    project: {
      description: 'Project of call';
      exampleValues: ['my-project'];
    };
    traceId: {
      description: 'ID of trace';
      exampleValues: ['bb5621fd-91bc-42af-b017-1a34e3250330'];
    };
    path: {
      description: 'Path of call';
      exampleValues: ['my-path'];
    };
    isParentRow: {
      description: 'Whether the cell clicked is a parent row';
      exampleValues: [true, false];
    };
    hierarchyDepth: {
      description: 'Depth of the hierarchy';
      exampleValues: [1, 2, 3];
    };
  }
>('Weave call tree cell clicked');

export const metricsPlotsViewed = makeTrackEvent<
  {
    entity: string;
    project: string;
    latency: number;
  },
  {
    _description: `User viewed metrics plots`;
    _location: '';
    _motivation: 'Used for tracking metrics plots';
    entity: {
      description: 'Entity of call';
      exampleValues: ['my-entity'];
    };
    project: {
      description: 'Project of call';
      exampleValues: ['my-project'];
    };
    latency: {
      description: 'Latency of calls stream query (ms)';
      exampleValues: [1000, 500];
    };
  }
>('Weave metrics plots viewed');

export const dateFilterDropdownUsed = makeTrackEvent<
  {
    entity: string;
    project: string;
    rawInput: string;
    date: string;
  },
  {
    _description: `User used the date filter dropdown`;
    _location: '';
    _motivation: 'Used for tracking date filter dropdown usage';
    entity: {
      description: 'Entity of call';
      exampleValues: ['my-entity'];
    };
    project: {
      description: 'Project of call';
      exampleValues: ['my-project'];
    };
    rawInput: {
      description: 'Raw input of date filter';
      exampleValues: ['7d', '1m', '1y', '2024-01-01'];
    };
    date: {
      description: 'Date of call';
      exampleValues: ['2024-01-01', '2024-01-02'];
    };
  }
>('Weave date filter dropdown used');

export const colabButtonClicked = makeTrackEvent<
  {
    userId: string;
    organizationName: string;
    entityName: string;
    projectName: string;
    source: string;
    url: string;
  },
  {
    _description: `User clicked the 'Get started with Colab' button`;
    _location: '';
    _motivation: 'Used for tracking Colab tutorial engagement';
    userId: {
      description: 'ID of user clicking the button';
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
    projectName: {
      description: 'Name of project where the button was clicked';
      exampleValues: ['my-project'];
    };
    source: {
      description: 'Location where the Colab button was clicked';
      exampleValues: ['traces_empty_state', 'evaluations_empty_state'];
    };
    url: {
      description: 'URL of the Colab notebook being accessed';
      exampleValues: [
        'https://colab.research.google.com/github/wandb/weave/blob/master/docs/notebooks/Intro_to_Weave_Hello_Trace.ipynb'
      ];
    };
  }
>('Weave colab link clicked');

export const docsLinkClicked = makeTrackEvent<
  {
    userId: string;
    organizationName: string;
    entityName: string;
    projectName: string;
    source: string;
    docType: string;
    url: string;
  },
  {
    _description: `User clicked a documentation link during onboarding`;
    _location: '';
    _motivation: 'Used for tracking documentation engagement during onboarding';
    userId: {
      description: 'ID of user clicking the link';
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
    projectName: {
      description: 'Name of project where the link was clicked';
      exampleValues: ['my-project'];
    };
    source: {
      description: 'Location where the docs link was clicked';
      exampleValues: ['traces_empty_state', 'evaluations_empty_state'];
    };
    docType: {
      description: 'Type of documentation being accessed';
      exampleValues: [
        'tracing_basics',
        'quickstart_guide',
        'evaluation_basics'
      ];
    };
    url: {
      description: 'URL of the documentation being accessed';
      exampleValues: [
        'http://wandb.me/weave_traces',
        'http://wandb.me/weave_quickstart'
      ];
    };
  }
>('Weave docs link clicked');

export const openConfigureProviderDrawer = makeTrackEvent<
  {
    userId: string;
    organizationName: string;
    entityName: string;
    projectName: string;
    source: string;
    provider: string;
  },
  {
    _description: `User opened the LLM provider configuration drawer`;
    _location: '';
    _motivation: 'Used for tracking LLM provider configuration engagement';
    userId: {
      description: 'ID of user clicking the button';
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
    projectName: {
      description: 'Name of project where the button was clicked';
      exampleValues: ['my-project'];
    };
    source: {
      description: 'Location where the configure button was clicked';
      exampleValues: ['llm_playground_empty_state', 'llm_dropdown'];
    };
    provider: {
      description: 'The provider being configured';
      exampleValues: ['openai', 'anthropic', 'custom-provider'];
    };
  }
>('Weave playground provider config drawer clicked');

export const providerUpdated = makeTrackEvent<
  {
    userId: string;
    organizationName: string;
    entityName: string;
    projectName: string;
    source: string;
    providerName: string;
    isNewProvider: boolean;
    numModels?: number;
  },
  {
    _description: `User added or updated an AI provider`;
    _location: '';
    _motivation: 'Used for tracking provider configuration changes';
    userId: {
      description: 'ID of user configuring the provider';
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
    projectName: {
      description: 'Name of project';
      exampleValues: ['my-project'];
    };
    source: {
      description: 'Location where the provider was configured';
      exampleValues: ['playground_drawer', 'settings_page'];
    };
    providerName: {
      description: 'Name of the provider being configured';
      exampleValues: ['openai', 'anthropic', 'custom-provider'];
    };
    isNewProvider: {
      description: 'Whether this is a new provider being added (true) or an update to an existing one (false)';
      exampleValues: [true, false];
    };
    numModels: {
      description: 'Optional: Number of models configured for this provider';
      exampleValues: [1, 2, 3];
    };
  }
>('Weave playground provider added or updated');
