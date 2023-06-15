import fetch from 'isomorphic-unfetch';

import type {TypedDictType} from '../../model';
import {hash, list, typedDict} from '../../model';
import {makeOp} from '../../opStore';
import {docType} from '../../util/docs';
import {makeTaggingStandardOp} from '../opKinds';
import {gqlArgs, gqlObjectField, toGqlQuery} from './gql';
import {connectionToNodes} from './util';

const entityNameArgDescription = `The name of a ${docType('user')} or ${docType(
  'org'
)}`;
const projectNameArgDescription = `The name of the ${docType('project')}`;
const artifactTypeNameArgDescription = `The type name of the ${docType(
  'artifactType'
)}`;
const artifactVersionNameArgDescription = `The version name of the ${docType(
  'artifact'
)}: \`<ArtifactName>:<version>\``;
const orgNameArgDescription = `The name of the ${docType('org')}`;
const userNameArgDescription = `The name of the ${docType('user')}`;

// Note, these are all hidden for now! But we do use opRootArtifact
// to fetch tables now, so users do interact with these.
export const opRootEntity = makeTaggingStandardOp({
  hidden: true,
  name: 'root-entity',
  argTypes: {entityName: 'string'},
  description: `Directly fetch a ${docType('entity')} by name`,
  argDescriptions: {
    entityName: entityNameArgDescription,
  },
  renderInfo: {type: 'function'},
  returnValueDescription: `A ${docType('entity')}`,
  returnType: () => 'entity',
  resolver: async (
    inputs,
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context
  ) => {
    const query = {
      queryFields: toGqlQuery(forwardGraph, forwardOp),
    };
    const result = await context.backend.execute(query);
    const alias = `entity_${hash(inputs.entityName)}`;
    const out = result[alias];
    return out;
  },
});

export const opRootProject = makeTaggingStandardOp({
  // hidden: true,
  name: 'root-project',
  argTypes: {entityName: 'string', projectName: 'string'},
  description: `Directly fetch a ${docType('project')}`,
  argDescriptions: {
    entityName: entityNameArgDescription,
    projectName: projectNameArgDescription,
  },
  returnValueDescription: `A ${docType('project')}`,
  returnType: () => 'project',
  renderInfo: {type: 'function'},
  resolver: async (
    inputs,
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context
  ) => {
    const query = {
      queryFields: toGqlQuery(forwardGraph, forwardOp),
    };
    const result = await context.backend.execute(query);
    const alias = `project_${hash(
      inputs.entityName + '/' + inputs.projectName
    )}`;
    return result[alias];
  },
});

export const opRootArtifactVersion = makeOp({
  hidden: true,
  name: 'root-artifactVersion',
  argTypes: {
    entityName: 'string',
    projectName: 'string',
    artifactTypeName: 'string',
    artifactVersionName: 'string',
  },
  description: `Directly fetch a ${docType('artifactVersion')}`,
  argDescriptions: {
    entityName: entityNameArgDescription,
    projectName: projectNameArgDescription,
    artifactTypeName: artifactTypeNameArgDescription,
    artifactVersionName: artifactVersionNameArgDescription,
  },
  returnValueDescription: `A ${docType('artifactVersion')}`,
  returnType: 'artifactVersion',
  renderInfo: {type: 'function'},
  resolver: async (inputs, forwardGraph, forwardOp, context) => {
    const query = {
      queryFields: toGqlQuery(forwardGraph, forwardOp),
    };
    const result = await context.backend.execute(query);
    const projectAlias = `project_${hash(
      inputs.entityName + '/' + inputs.projectName
    )}`;
    const artifactTypeAlias = `artifactType_${hash(inputs.artifactTypeName)}`;
    const artifactAlias = `artifact_${hash(inputs.artifactVersionName)}`;
    return result?.[projectAlias]?.[artifactTypeAlias]?.[artifactAlias];
  },
});

export const opRootOrg = makeOp({
  hidden: true,
  name: 'root-org',
  argTypes: {orgName: 'string'},
  description: `Directly fetch a ${docType('org')}`,
  argDescriptions: {
    orgName: orgNameArgDescription,
  },
  returnValueDescription: `A ${docType('org')}`,
  returnType: 'org',
  renderInfo: {type: 'function'},
  resolver: async (inputs, forwardGraph, forwardOp, context) => {
    const query = {
      queryFields: toGqlQuery(forwardGraph, forwardOp),
    };
    const result = await context.backend.execute(query);
    const alias = `organization_${hash(inputs.orgName)}`;
    return result[alias];
  },
});

export const opRootUser = makeOp({
  hidden: true,
  name: 'root-user',
  argTypes: {userName: 'string'},
  description: `Directly fetch a ${docType('user')}`,
  argDescriptions: {
    userName: userNameArgDescription,
  },
  returnValueDescription: `A ${docType('user')}`,
  returnType: 'user',
  renderInfo: {type: 'function'},
  resolver: async (inputs, forwardGraph, forwardOp, context) => {
    const query = {
      queryFields: toGqlQuery(forwardGraph, forwardOp),
    };
    const result = await context.backend.execute(query);
    const alias = `user_${hash(inputs.userName)}`;
    return result[alias];
  },
});

// I don't think we should expose this, it would allow users to make
// queries that depend based on who is looking. But we can use it to suggest
// potentially useful things for the current viewer in suggest.ts
export const opRootViewer = makeOp({
  hidden: true,
  name: 'root-viewer',
  argTypes: {},
  description: `Directly fetch the current ${docType('user')}`,
  argDescriptions: {},
  returnValueDescription: `Current ${docType('user')}`,
  returnType: 'user',
  resolver: async (inputs, forwardGraph, forwardOp, context) => {
    const query = {
      queryFields: toGqlQuery(forwardGraph, forwardOp),
    };
    const result = await context.backend.execute(query);
    return result.viewer;
  },
});

export const opRootFeaturedReports = makeOp({
  hidden: true,
  name: 'root-featuredreports',
  argTypes: {},
  returnType: {type: 'list', objectType: 'report'},
  renderInfo: {type: 'function'},
  description: `Directly fetch the featured ${docType('report', {
    plural: true,
  })}`,
  argDescriptions: {},
  returnValueDescription: `A ${docType('list')} of featured ${docType(
    'report',
    {plural: true}
  )}`,
  resolver: async (inputs, forwardGraph, forwardOp, context) => {
    const featuredReportsQuery = {
      queryFields: [
        {
          name: 'featuredReports',
          fields: [
            {name: 'id', fields: []},
            {name: 'spec', fields: []},
          ],
        },
      ],
    };
    const featuredReportsResult = await context.backend.execute(
      featuredReportsQuery
    );
    const parsed = JSON.parse(featuredReportsResult.featuredReports.spec);
    const reportIds = parsed.reports.map((report: any) => report.id);
    const query = {
      queryFields: [
        {
          name: 'views',
          args: gqlArgs({ids: reportIds}),
          fields: [
            {
              name: 'edges',
              fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
            },
          ],
        },
      ],
    };
    const result = await context.backend.execute(query);
    return connectionToNodes(result.views);
  },
});

// Instance-wide root queries (hidden; for local activity dashboard only)
export const opRootAllProjects = makeOp({
  hidden: true,
  name: 'root-allProjects',
  argTypes: {},
  returnType: {type: 'list', objectType: 'project'},
  renderInfo: {type: 'function'},
  description: `Directly fetch all visible ${docType('project', {
    plural: true,
  })} - only available in local W&B deployments`,
  argDescriptions: {},
  returnValueDescription: `A ${docType('list')} of all visible ${docType(
    'project',
    {plural: true}
  )}`,
  resolver: async (inputs, forwardGraph, forwardOp, context) => {
    const query = {
      queryFields: toGqlQuery(forwardGraph, forwardOp),
    };
    const result = await context.backend.execute(query);
    return connectionToNodes(result?.instance?.projects);
  },
});

export const opRootAllReports = makeOp({
  hidden: true,
  name: 'root-allReports',
  argTypes: {},
  returnType: {type: 'list', objectType: 'report'},
  renderInfo: {type: 'function'},
  description: `Directly fetch all ${docType('report', {
    plural: true,
  })} - only available in local W&B deployments`,
  argDescriptions: {},
  returnValueDescription: `A ${docType('list')} of ${docType('report', {
    plural: true,
  })}`,
  resolver: async (inputs, forwardGraph, forwardOp, context) => {
    const query = {
      queryFields: toGqlQuery(forwardGraph, forwardOp),
    };
    const result = await context.backend.execute(query);
    return connectionToNodes(result?.instance?.views).filter(
      (edge: any) => edge.type === 'runs'
    );
  },
});

export const opRootAllArtifacts = makeOp({
  hidden: true,
  name: 'root-allArtifacts',
  argTypes: {},
  returnType: {type: 'list', objectType: 'artifact'},
  renderInfo: {type: 'function'},
  description: `Directly fetch all ${docType('artifact', {
    plural: true,
  })} - only available in local W&B deployments`,
  argDescriptions: {},
  returnValueDescription: `A ${docType('list')} of ${docType('artifact', {
    plural: true,
  })}`,
  resolver: async (inputs, forwardGraph, forwardOp, context) => {
    const query = {
      queryFields: toGqlQuery(forwardGraph, forwardOp),
    };
    const result = await context.backend.execute(query);
    return connectionToNodes(result?.instance?.artifactSequences);
  },
});

export const opRootAllEntities = makeOp({
  hidden: true,
  name: 'root-allEntities',
  argTypes: {},
  returnType: {type: 'list', objectType: 'entity'},
  renderInfo: {type: 'function'},
  description: `Directly fetch all ${docType('entity', {
    plural: true,
  })} - only available in local W&B deployments`,
  argDescriptions: {},
  returnValueDescription: `A ${docType('list')} of ${docType('entity', {
    plural: true,
  })}`,
  resolver: async (inputs, forwardGraph, forwardOp, context) => {
    const query = {
      queryFields: toGqlQuery(forwardGraph, forwardOp),
    };
    const result = await context.backend.execute(query);
    return result?.instance?.entities;
  },
});

export const repoInsightsRowTypes = {
  rpt_weekly_users_by_country_by_repo: typedDict({
    user_fraction: 'number' as const,
    country: 'string' as const,
    created_week: 'date' as const,
    framework: 'string' as const,
  }),
  rpt_weekly_repo_users_by_persona: typedDict({
    created_week: 'date' as const,
    framework: 'string' as const,
    persona: 'string' as const,
    percentage: 'number' as const,
  }),
  rpt_weekly_engaged_user_count_by_repo: typedDict({
    created_week: 'date' as const,
    framework: 'string' as const,
    user_count: 'number' as const,
  }),
  rpt_repo_gpu_backends: typedDict({
    created_week: 'date' as const,
    framework: 'string' as const,
    gpu: 'string' as const,
    percentage: 'number' as const,
  }),
  rpt_versus_other_repos: typedDict({
    created_week: 'date' as const,
    framework: 'string' as const,
    percentage: 'number' as const,
  }),
  rpt_runtime_buckets: typedDict({
    created_week: 'date' as const,
    framework: 'string' as const,
    bucket: 'string' as const,
    bucket_run_percentage: 'number' as const,
  }),
  rpt_user_model_train_freq: typedDict({
    created_week: 'date' as const,
    framework: 'string' as const,
    train_freq: 'string' as const,
    percentage: 'number' as const,
  }),
  rpt_runs_versus_other_repos: typedDict({
    created_week: 'date' as const,
    framework: 'string' as const,
    percentage: 'number' as const,
  }),
  rpt_product_usage: typedDict({
    created_week: 'date' as const,
    framework: 'string' as const,
    product: 'string' as const,
    percentage: 'number' as const,
  }),
};

const makeRepoInsightsOp = (plotName: string, outputRowType: TypedDictType) => {
  return makeOp({
    hidden: true,
    name: plotName,
    argTypes: {
      repoName: 'string',
    },
    description: `Fetch the data needed to render the ${plotName} plot for a given repo`,
    argDescriptions: {
      repoName: `The name of the repo to fetch data for`,
    },
    returnValueDescription: ``,
    returnType: typedDict({
      rows: {type: 'list', objectType: outputRowType},
      isNormalizedUserCount: 'boolean',
    }),
    renderInfo: {type: 'function'},
    resolver: async (inputs, forwardGraph, forwardOp, context) => {
      const query = {
        queryFields: toGqlQuery(forwardGraph, forwardOp),
      };

      const result = await context.backend.execute(query);
      const alias = `repoInsights_${hash(inputs.repoName)}_${hash(plotName)}`;

      const schema: Array<{
        Name: string;
        Repeated: boolean;
        Required: boolean;
        Type: string;
      }> = result[alias]?.schema;
      if (!schema) {
        throw new Error(`No schema for ${alias}`);
      }

      const processRow = (row: any[]): {[key: string]: any} => {
        const processedRow: {[key: string]: any} = {};
        for (let i = 0; i < schema.length; i++) {
          // TODO(dag): Handle repeated and required
          const {Name: name, Type: type} = schema[i];
          if (type === 'TIMESTAMP') {
            processedRow[name] = new Date(row[i]);
          } else {
            processedRow[name] = row[i];
          }
        }
        return processedRow;
      };

      const rows = connectionToNodes(result[alias]).map((node: any) =>
        processRow(node.row)
      );

      const isNormalizedUserCount = result[alias]?.isNormalizedUserCount;
      return {rows, isNormalizedUserCount};
    },
  });
};

export const opRootRepoInsightsUsersByCountry = makeRepoInsightsOp(
  'rpt_weekly_users_by_country_by_repo',
  repoInsightsRowTypes.rpt_weekly_users_by_country_by_repo
);

export const opRootRepoInsightsUsersByPersona = makeRepoInsightsOp(
  'rpt_weekly_repo_users_by_persona',
  repoInsightsRowTypes.rpt_weekly_repo_users_by_persona
);

export const opRootRepoInsightsWeeklyEngagedUserCount = makeRepoInsightsOp(
  'rpt_weekly_engaged_user_count_by_repo',
  repoInsightsRowTypes.rpt_weekly_engaged_user_count_by_repo
);

export const opRootRepoInsightsGpuBackend = makeRepoInsightsOp(
  'rpt_repo_gpu_backends',
  repoInsightsRowTypes.rpt_repo_gpu_backends
);

export const opRootRepoInsightsVersusOtherRepos = makeRepoInsightsOp(
  'rpt_versus_other_repos',
  repoInsightsRowTypes.rpt_versus_other_repos
);

export const opRootRepoInsightsWeeklyRuntimeBuckets = makeRepoInsightsOp(
  'rpt_runtime_buckets',
  repoInsightsRowTypes.rpt_runtime_buckets
);

export const opRootRepoInsightsWeeklyModelTrainFreq = makeRepoInsightsOp(
  'rpt_user_model_train_freq',
  repoInsightsRowTypes.rpt_user_model_train_freq
);

export const opRootRepoInsightsRunsVersusOtherRepos = makeRepoInsightsOp(
  'rpt_runs_versus_other_repos',
  repoInsightsRowTypes.rpt_runs_versus_other_repos
);

export const opRootRepoInsightsProductUsage = makeRepoInsightsOp(
  'rpt_product_usage',
  repoInsightsRowTypes.rpt_product_usage
);

export const opRootAuditLogs = makeOp({
  hidden: true,
  name: 'root-_root_audit_logs_',
  argTypes: {
    url: 'string' as const,
    numDays: 'number' as const,
    anonymize: 'boolean' as const,
  },
  returnType: typedDict({
    data: list(
      typedDict({
        // AuditLog
        timestamp: 'string' as const,
        action: 'string' as const,

        // DeanomizedContext
        actor_email: 'string' as const,
        user_email: 'string' as const,
        entity_name: 'string' as const,
        project_name: 'string' as const,
        report_name: 'string' as const,
        artifact_digest: 'string' as const,
        artifact_sequence_name: 'string' as const,
        artifact_version_index: 'number' as const,

        // StaticContext
        response_code: 'number' as const,
        cli_version: 'string' as const,
        actor_ip: 'string' as const,

        // AuditLog but less prominent
        actor_user_id: 'number' as const,
        audit_log_error: 'string' as const,

        // StaticContext but deanonymized
        entity_asset: 'number' as const,
        user_asset: 'number' as const,
        artifact_asset: 'number' as const,
        artifact_sequence_asset: 'number' as const,
        project_asset: 'number' as const,
        report_asset: 'number' as const,
      })
    ),
    error: 'string' as const,
  }),
  renderInfo: {type: 'function'},
  description: `Directly fetch all ${docType('artifact', {
    plural: true,
  })} - only available in local W&B deployments`,
  argDescriptions: {},
  returnValueDescription: `A ${docType('list')} of ${docType('artifact', {
    plural: true,
  })}`,
  resolver: async (inputs, forwardGraph, forwardOp, context) => {
    // check if cache has data
    const cacheKey = inputs.url + inputs.numDays + inputs.anonymize;
    const cachedData = auditLogDataCache.get(cacheKey);
    if (cachedData) {
      const {data: data1, time} = cachedData;
      const now = new Date().getTime();
      // if data is less than 5 minutes old, return it
      if (now - time < 5 * 60 * 1000) {
        return {data: data1, error: ''};
      }
    }

    // if cache is empty or data is more than 5 minutes old, fetch data
    const {data, error} = await getAuditLogData(
      inputs.url,
      inputs.numDays,
      inputs.anonymize
    );

    // if no error, set the data in cache
    if (error.length === 0) {
      auditLogDataCache.set(cacheKey, {data, time: new Date().getTime()});
    }

    return {data, error};
  },
});

// add cache to audit log data
const auditLogDataCache = new Map<string, {data: any[]; time: number}>();

const getAuditLogData = async (
  url: string,
  numDays: number,
  anonymize: boolean
) => {
  try {
    const req = url + '?numDays=' + numDays + '&anonymize=' + anonymize;
    // eslint-disable-next-line wandb/no-unprefixed-urls
    const res = await fetch(req, {method: 'GET'});
    if (!res.ok) {
      return {data: [], error: 'res is not ok: ' + (await res.text())};
    } else {
      const text = await res.text();
      const lines = text.split('\n');
      const data = lines
        .filter((line: string) => line.length > 0)
        .map((line: string) => JSON.parse(line));
      return {data, error: ''};
    }
  } catch (e) {
    return {data: [], error: 'error parsing audit log data: ' + String(e)};
  }
};
