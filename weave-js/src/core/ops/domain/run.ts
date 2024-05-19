import * as _ from 'lodash';

import * as Urls from '../../_external/util/urls';
import * as callFunction from '../../callers';
import {Client, EngineClient} from '../../client';
import {Engine} from '../../engine';
import {refineNode} from '../../hl';
import {nullableTaggableStrip} from '../../model';
import {constNode, constNumber} from '../../model/graph/construction';
import * as GraphTypes from '../../model/graph/types';
import * as TypeHelpers from '../../model/helpers';
import * as Types from '../../model/types';
import {jsValToCGType, replaceInputVariables} from '../../refineHelpers';
import {docType} from '../../util/docs';
import * as JSONNan from '../../util/jsonnan';
import * as Obj from '../../util/obj';
import * as String from '../../util/string';
import * as OpKinds from '../opKinds';
import {connectionToNodes} from './util';

const makeRunOp = OpKinds.makeTaggingStandardOp;

const runArgTypes = {
  run: 'run' as const,
};

const runArgDescriptions = `A ${docType('run')}`;

const isTableTypeHistoryKeyType = (id: string) => {
  return ['table-file', 'partitioned-table', 'joined-table'].includes(id);
};

export const opGetRunTag = OpKinds.makeTagGetterOp({
  name: 'tag-run',
  tagName: 'run',
  tagType: 'run',
});

export const opRunInternalId = makeRunOp({
  hidden: true,
  name: 'run-internalId',
  argTypes: runArgTypes,
  description: `Returns the internal id of the ${docType('run')}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The internal id of the ${docType('run')}`,
  returnType: inputTypes => 'string',
  resolver: ({run}) => {
    return run.id;
  },
});

// Keep this hidden until we're sure users need it.
export const opRunId = makeRunOp({
  hidden: true,
  name: 'run-id',
  argTypes: runArgTypes,
  description: `Returns the id of the ${docType('run')}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The id of the ${docType('run')}`,
  returnType: inputTypes => 'string',
  resolver: ({run}) => run.name,
});

export const opRunName = makeRunOp({
  name: 'run-name',
  argTypes: runArgTypes,
  description: `Returns the name of the ${docType('run')}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The name of the ${docType('run')}`,
  returnType: inputTypes => 'string',
  resolver: ({run}) => run.displayName,
});

export const opRunJobType = makeRunOp({
  name: 'run-jobType',
  argTypes: runArgTypes,
  description: `Returns the job type of the ${docType('run')}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The job type of the ${docType('run')}`,
  returnType: inputTypes => 'string',
  resolver: ({run}) => run.jobType,
});

export const opRunLink = makeRunOp({
  hidden: true,
  name: 'run-link',
  argTypes: runArgTypes,
  description: `Returns the link to the ${docType('run')}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The link to the ${docType('run')}`,
  returnType: inputTypes => 'link',
  resolver: ({run}) => ({
    name: run.displayName,
    url: Urls.run({
      entityName: run.project.entityName,
      projectName: run.project.name,
      name: run.name,
    }),
  }),
});

export const opRunProject = makeRunOp({
  hidden: true,
  name: 'run-project',
  argTypes: runArgTypes,
  description: `Returns the ${docType('project')} of the ${docType('run')}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The ${docType('project')} of the ${docType('run')}`,
  returnType: inputTypes => 'project',
  resolver: ({run}) => run.project,
});

export const opRunUser = makeRunOp({
  name: 'run-user',
  argTypes: runArgTypes,
  description: `Returns the ${docType('user')} of the ${docType('run')}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The ${docType('user')} of the ${docType('run')}`,
  returnType: inputTypes => 'user',
  resolver: ({run}) => run.user,
});

export const opRunCreatedAt = makeRunOp({
  name: 'run-createdAt',
  argTypes: runArgTypes,
  description: `Returns the created at datetime of the ${docType('run')}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The created at datetime of the ${docType('run')}`,
  returnType: inputTypes => 'date',
  resolver: ({run}) => new Date(run.createdAt + 'Z'),
});

export const opRunUpdatedAt = makeRunOp({
  name: 'run-updatedAt',
  hidden: true,
  argTypes: runArgTypes,
  description: `Returns the updated at datetime of the ${docType('run')}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The updated at datetime of the ${docType('run')}`,
  returnType: inputTypes => 'date',
  resolver: ({run}) => new Date(run.updatedAt + 'Z'),
});

export const opRunHeartbeatAt = makeRunOp({
  name: 'run-heartbeatAt',
  argTypes: runArgTypes,
  description: `Returns the last heartbeat datetime of the ${docType('run')}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The last heartbeat datetime of the ${docType(
    'run'
  )}`,
  returnType: inputTypes => 'date',
  resolver: ({run}) => new Date(run.heartbeatAt + 'Z'),
});

// Hiding... does job type want to be something more than a string?
export const opRunJobtype = makeRunOp({
  hidden: true,
  name: 'run-jobtype',
  argTypes: runArgTypes,
  description: `Returns the job type of the ${docType('run')}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The job type of the ${docType('run')}`,
  returnType: inputTypes => 'string',
  resolver: ({run}) => run.jobType,
});

// Create a Type from config or summary json.
// Note: this is not complete! It doesn't handle nested keys
// at all.
export const wandbJsonType = (json: any): Types.Type => {
  const propertyTypes: {[key: string]: Types.Type} = {};
  for (const key of Object.keys(json ?? {})) {
    propertyTypes[key] = jsValToCGType(json[key]);
  }
  return {type: 'typedDict', propertyTypes};
};

export const wandbJsonWithArtifacts = (json: {[key: string]: any}) => {
  return _.mapValues(json, val => {
    if (
      val != null &&
      isTableTypeHistoryKeyType(val._type) &&
      val.artifact_path != null
    ) {
      const parsedRef = TypeHelpers.parseArtifactRef(val.artifact_path);
      return {
        ...val,
        artifact: {id: parsedRef.artifactId},
        path: parsedRef.assetPath,
      };
    }
    return val;
  });
};

const removeWandbKeys = (json: {[key: string]: any}) => {
  return _.pickBy(json, (val, key) => key !== '_wandb');
};

export const opRunConfig = makeRunOp({
  name: 'run-config',
  argTypes: runArgTypes,
  description: `Returns the config ${docType('typedDict')} of the ${docType(
    'run'
  )}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The config ${docType('typedDict')} of the ${docType(
    'run'
  )}`,
  returnType: inputTypes => TypeHelpers.typedDict({}),
  resolver: ({run}) => {
    const parsed = JSONNan.JSONparseNaN(run.config) ?? {};
    const fixed = _.mapValues(parsed, (child: any) => child.value);
    return wandbJsonWithArtifacts(removeWandbKeys(fixed));
  },
  // TODO: resolveOutputType does not perform all the correct
  // unwrapping!
  resolveOutputType: async (inputTypes, node, executableNode, client) => {
    const runConfigNode = replaceInputVariables(executableNode, client.opStore);
    const config: any = await client.query(runConfigNode);
    if (_.isArray(config)) {
      if (config.length === 0) {
        // This will happen in cases that the incoming run list is empty!
        return TypeHelpers.typedDict({});
      }
      return TypeHelpers.union(config.map(wandbJsonType));
    } else {
      return wandbJsonType(config);
    }
  },
});

export const coerceSummaryMetricsStringToJSON = (
  summaryMetricsString?: string
): {[key: string]: any} => {
  return wandbJsonWithArtifacts(
    removeWandbKeys(JSONNan.JSONparseNaN(summaryMetricsString ?? '{}'))
  );
};

export const opRunSummaryType = OpKinds.makeBasicOp({
  hidden: true,
  name: 'refine_summary_type',
  argTypes: {
    run: TypeHelpers.nullableOneOrMany('run'),
  },
  description: `Returns the type of a ${docType('run')} summary.`,
  argDescriptions: {
    run: `A ${docType('run')}`,
  },
  returnValueDescription: `The type of the ${docType('run')} summary`,
  returnType: inputs => 'type',
  resolver: async ({run}) => {
    if (run == null) {
      return 'none';
    } else if (_.isArray(run)) {
      if (run.length === 0) {
        return TypeHelpers.list(TypeHelpers.typedDict({}));
      } else {
        return TypeHelpers.list(
          TypeHelpers.union(
            run.map(r =>
              wandbJsonType(
                coerceSummaryMetricsStringToJSON(
                  TypeHelpers.getValueFromTaggedValue(r).summaryMetrics
                )
              )
            )
          )
        );
      }
    } else {
      return wandbJsonType(
        coerceSummaryMetricsStringToJSON(run.summaryMetrics)
      );
    }
  },
});

export const opRunSummary = makeRunOp({
  name: 'run-summary',
  argTypes: runArgTypes,
  description: `Returns the summary ${docType('typedDict')} of the ${docType(
    'run'
  )}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The summary ${docType('typedDict')} of the ${docType(
    'run'
  )}`,
  returnType: inputTypes => TypeHelpers.typedDict({}),
  resolver: ({run}) => {
    const res = JSONNan.JSONparseNaN(run.summaryMetrics) ?? {};
    return wandbJsonWithArtifacts(removeWandbKeys(res));
  },

  // This TODO is important! Need to use the same OpTypes behaviors
  // we do in returnType in all resolveOutputType calls
  // TODO: resolveOutputType does not perform all the correct
  // unwrapping!

  resolveOutputType: async (inputTypes, node, executableNode, client) => {
    const runNode = replaceInputVariables(
      executableNode.fromOp.inputs.run,
      client.opStore
    );
    const refinedRunNode = await refineNode(client, runNode, []);
    const runSummaryType = opRunSummaryType({run: refinedRunNode});
    let result = nullableTaggableStrip(await client.query(runSummaryType));
    if (TypeHelpers.isListLike(refinedRunNode.type)) {
      result = TypeHelpers.listObjectType(result);
      result = nullableTaggableStrip(result);
    }
    return result;
  },
});

// TODO: missing test
export const opRunHistoryKeyInfo = makeRunOp({
  hidden: true,
  name: '_run-historykeyinfo',
  argTypes: runArgTypes,
  description: `Returns the history key info for each key of the ${docType(
    'run'
  )}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The history key info for each key of the ${docType(
    'run'
  )}`,
  returnType: inputTypes => TypeHelpers.typedDict({}),
  resolver: ({run}) => run.historyKeys ?? {keys: {}},
});

const opRunHistoryTypeResolver = async (run: any, engine: () => Engine) => {
  const client = new EngineClient(engine());

  // TODO: this may not be the right type (could be null, list(run), list(maybe(run)), etc. instead of just run)
  // but we dont actually need the right type here, just the right value
  const runNode = constNode('run', run);

  // Execute ourself!
  const runHistoryNode = opRunHistory({run: runNode});
  // TODO: This is very expensive right now! It reads the entire history
  // and all keys, for the table logic below. Totally unnecessary.
  const history = await client.query(runHistoryNode);
  const runHistoryTypeNode = opRunHistoryKeyInfo({run: runNode});
  const historyKeyInfo = await client.query(runHistoryTypeNode);
  const historyKeyInfoIsArray = _.isArray(historyKeyInfo);

  const typeFromHistoryAndKeyInfo = (h: any, hki: any): Types.Type => {
    const propertyTypes: {[key: string]: Types.Type} = {};
    for (const key of Object.keys(hki?.keys ?? {})) {
      const val = hki.keys[key];
      const valType = val.typeCounts[0].type;
      if (valType === 'string') {
        propertyTypes[key] = 'string';
      } else if (valType === 'number') {
        propertyTypes[key] = 'number';
      } else if (valType === 'wb_trace_tree') {
        propertyTypes[key] = {type: 'wb_trace_tree'};
      } else if (isTableTypeHistoryKeyType(valType)) {
        const vals = h.map((hRow: any) => hRow[key]).filter(Obj.notEmpty);
        if (vals.length !== 0) {
          const val0 = vals[0];
          if (val0.artifact_path == null) {
            // TODO: This will throw an error in the non-artifact case.
            // Shouldn't be an error. Ideally we'd load from the run.
            throw new Error(
              'opRunHistory: expected artifact_path to be non-null'
            );
          }
          if (isTableTypeHistoryKeyType(val0._type)) {
            if (val0.artifact_path != null) {
              propertyTypes[key] = TypeHelpers.filePathToType(
                TypeHelpers.parseArtifactRef(val0.artifact_path).assetPath
              );
            } else {
              propertyTypes[key] = TypeHelpers.filePathToType(val0.path);
            }
          }
        }
      }
    }
    return {
      type: 'list',
      objectType: {
        type: 'typedDict',
        propertyTypes,
      },
    };
  };

  return historyKeyInfoIsArray
    ? TypeHelpers.list(
        TypeHelpers.union(
          history.map((h: any, i: number) =>
            typeFromHistoryAndKeyInfo(h, historyKeyInfo[i])
          )
        )
      )
    : typeFromHistoryAndKeyInfo(history, historyKeyInfo);
};

export const opRunHistoryType = OpKinds.makeBasicOp({
  hidden: true,
  name: 'refine_history_type',
  argTypes: {
    run: TypeHelpers.nullableOneOrMany('run'),
  },
  description: `Returns the type of a ${docType('run')} history.`,
  argDescriptions: {
    run: `A ${docType('run')}`,
  },
  returnValueDescription: `The type of the ${docType('run')} history`,
  returnType: inputs => 'type',
  resolver: async (
    {run},
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context,
    engine
  ) => opRunHistoryTypeResolver(run, engine),
});

export const opRunHistoryType2 = OpKinds.makeBasicOp({
  hidden: true,
  name: 'refine_history2_type',
  argTypes: {
    run: TypeHelpers.nullableOneOrMany('run'),
  },
  description: `Returns the type of a ${docType('run')} history.`,
  argDescriptions: {
    run: `A ${docType('run')}`,
  },
  returnValueDescription: `The type of the ${docType('run')} history`,
  returnType: inputs => 'type',
  resolver: async (
    {run},
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context,
    engine
  ) => opRunHistoryTypeResolver(run, engine),
});

export const opRunHistoryType3 = OpKinds.makeBasicOp({
  hidden: true,
  name: 'refine_history3_type',
  argTypes: {
    run: TypeHelpers.nullableOneOrMany('run'),
  },
  description: `Returns the type of a ${docType('run')} history.`,
  argDescriptions: {
    run: `A ${docType('run')}`,
  },
  returnValueDescription: `The type of the ${docType('run')} history`,
  returnType: inputs => 'type',
  resolver: async (
    {run},
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context,
    engine
  ) => opRunHistoryTypeResolver(run, engine),
});

const opRunHistoryResolveOutputType = async (
  executableNode: GraphTypes.OutputNode<Types.Type>,
  client: Client,
  historyVersion: 1 | 2 | 3
) => {
  // See opRunSummary for comment

  // TODO: We don't need this firstRunNode thing here... This function is
  // just all wrong now. See more correct implementation in opRunSummary/
  // opRunConfig
  const firstRunNode = callFunction.mapNodes(executableNode, mapped => {
    if (
      mapped.nodeType === 'output' &&
      mapped.fromOp.name === 'index' &&
      mapped.fromOp.inputs.index.nodeType === 'var'
    ) {
      return {
        nodeType: 'output',
        // wrong type, but we don't need type to execute
        // the summary call... TODO: there must be a
        // better way
        type: 'invalid',
        fromOp: {
          ...mapped.fromOp,
          inputs: {
            ...mapped.fromOp.inputs,
            index: constNumber(0),
          },
        },
      };
    }
    return mapped;
  }) as GraphTypes.OutputNode;
  const run = firstRunNode.fromOp.inputs.run;
  const refinedRunNode = await refineNode(client, run, []);

  let result = nullableTaggableStrip(
    historyVersion === 1
      ? await client.query(opRunHistoryType({run}))
      : historyVersion === 2
      ? await client.query(opRunHistoryType2({run}))
      : await client.query(opRunHistoryType3({run}))
  );

  if (TypeHelpers.isListLike(refinedRunNode.type)) {
    result = TypeHelpers.listObjectType(result);
    result = nullableTaggableStrip(result);
  }

  return result;
};

const opRunHistoryResolver = (run: any) => {
  return (
    run?.history?.map((row: string) => {
      const res = JSONNan.JSONparseNaN(row);
      return wandbJsonWithArtifacts(res);
    }) ?? []
  );
};

// TODO: missing test
export const opRunHistory = makeRunOp({
  name: 'run-history',
  argTypes: runArgTypes,
  description: `Returns the log history of the ${docType('run')}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The log history of the ${docType('run')}`,
  returnType: inputTypes => TypeHelpers.list(TypeHelpers.typedDict({})),
  resolver: ({run}) => opRunHistoryResolver(run),
  // TODO: resolveOutputType does not perform all the correct
  // unwrapping!

  resolveOutputType: async (inputTypes, node, executableNode, client) => {
    return opRunHistoryResolveOutputType(executableNode, client, 1);
  },
});

// TODO: missing test
export const opRunHistory2 = makeRunOp({
  name: 'run-history2',
  argTypes: runArgTypes,
  description: `Returns the log history of the ${docType('run')}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The log history of the ${docType('run')}`,
  returnType: inputTypes => TypeHelpers.list(TypeHelpers.typedDict({})),
  hidden: true,
  resolver: ({run}) => opRunHistoryResolver(run),
  // TODO: resolveOutputType does not perform all the correct
  // unwrapping!

  resolveOutputType: async (inputTypes, node, executableNode, client) => {
    return opRunHistoryResolveOutputType(executableNode, client, 2);
  },
});

// This is just here so we can type history3 in the EE outside of weave.wandb.ai for testing
export const opRunHistory3 = makeRunOp({
  name: 'run-history3',
  argTypes: runArgTypes,
  description: `Returns the log history of the ${docType('run')}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The log history of the ${docType('run')}`,
  returnType: inputTypes => TypeHelpers.list(TypeHelpers.typedDict({})),
  hidden: true,
  resolver: ({run}) => opRunHistoryResolver(run),
  resolveOutputType: async (inputTypes, node, executableNode, client) => {
    return opRunHistoryResolveOutputType(executableNode, client, 3);
  },
});

export const opRunHistoryAsOfStep = makeRunOp({
  hidden: true,
  name: 'run-historyAsOf',
  argTypes: {
    run: 'run' as const,
    asOfStep: 'number' as const,
  },
  returnType: inputTypes => TypeHelpers.list(TypeHelpers.typedDict({})),
  resolver: ({run, asOfStep}) => {
    const returnedHistory = run?.[`historyAsOf_${asOfStep}`];
    if (returnedHistory == null) {
      return {};
    } else {
      return wandbJsonWithArtifacts(JSONNan.JSONparseNaN(returnedHistory[0]));
    }
  },

  resolveOutputType: async (inputTypes, node, executableNode, client) => {
    const history = await client.query(
      replaceInputVariables(executableNode, client.opStore)
    );
    if (_.isArray(history)) {
      if (history.length === 0) {
        // This will happen in cases that the incoming run list is empty!
        return TypeHelpers.typedDict({});
      }
      return TypeHelpers.union(history.map(wandbJsonType));
    } else {
      return wandbJsonType(history);
    }
  },
});

export const opRunLoggedArtifactVersion = makeRunOp({
  name: 'run-loggedArtifactVersion',
  argTypes: {...runArgTypes, artifactVersionName: 'string'},
  description: `Returns the ${docType(
    'artifactVersion'
  )} logged by the ${docType('run')} for a given name and alias`,
  argDescriptions: {
    run: runArgDescriptions,
    artifactVersionName: `The name:alias of the ${docType('artifactVersion')}`,
  },
  returnValueDescription: `The ${docType(
    'artifactVersion'
  )} logged by the ${docType('run')} for a given name and alias`,
  returnType: inputTypes => 'artifactVersion',
  resolver: ({run, artifactVersionName}) => {
    // tslint:disable-next-line: prefer-const
    let [artifactName, version] = String.splitOnce(artifactVersionName, ':');
    if (version == null) {
      version = 'latest';
    }
    const foundNode = connectionToNodes(run.outputArtifacts).find(
      (node: any) =>
        (node.versionIndex.toString() === version?.slice(1) ||
          node.aliases.some((a: any) => a.alias === version)) &&
        node.artifactSequence.name === artifactName
    );
    if (foundNode == null) {
      // We don't want to error here. in the case that you have
      // runs.loggedArtifactVersion("a:v1"), not all runs will
      // have the version.
      return null;
    }
    return foundNode;
  },
});

export const opRunLoggedArtifactVersions = makeRunOp({
  name: 'run-loggedArtifactVersions',
  argTypes: runArgTypes,
  description: `Returns all of the ${docType('artifactVersion', {
    plural: true,
  })} logged by the ${docType('run')}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The ${docType('artifactVersion', {
    plural: true,
  })} logged by the ${docType('run')}`,
  returnType: inputTypes => TypeHelpers.list('artifactVersion'),
  resolver: ({run}) => connectionToNodes(run.outputArtifacts),
});

export const opRunUsedArtifactVersions = makeRunOp({
  name: 'run-usedArtifactVersions',
  argTypes: runArgTypes,
  description: `Returns all of the ${docType('artifactVersion', {
    plural: true,
  })} used by the ${docType('run')}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The ${docType('artifactVersion', {
    plural: true,
  })} used by the ${docType('run')}`,
  returnType: inputTypes => TypeHelpers.list('artifactVersion'),
  resolver: ({run}) => connectionToNodes(run.inputArtifacts),
});

export const opRunRuntime = makeRunOp({
  name: 'run-runtime',
  argTypes: runArgTypes,
  description: `Returns the runtime in seconds of the ${docType('run')}`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The runtime in seconds of the ${docType('run')}`,
  returnType: inputTypes => 'number',
  resolver: ({run}) => {
    return run.computeSeconds;
  },
});

export const opStrRunlink = OpKinds.makeBasicOp({
  name: 'constructor-wbRunLink',
  hidden: true,
  argTypes: {
    entity_name: {
      type: 'union' as const,
      members: ['none' as const, 'string' as const],
    },
    project_name: {
      type: 'union' as const,
      members: ['none' as const, 'string' as const],
    },
    name: {
      type: 'union' as const,
      members: ['none' as const, 'string' as const],
    },
  },
  description: `Returns a link to the ${docType('run')} overview`,
  argDescriptions: {run: runArgDescriptions},
  returnValueDescription: `The link to the ${docType('run')} overview`,
  returnType: inputTypes => 'link',
  resolver: ({entity_name, project_name, name}) => {
    throw new Error('Attempting to use python-only op in js');
  },
});
