import * as _ from 'lodash';

import * as Vega3 from '../../_external/util/vega3';
import type {ForwardGraph, ForwardOp} from '../../engine/forwardGraph';
import {forwardOpInputs, newRefForwardGraph} from '../../engine/forwardGraph';
import {hash} from '../../model';
import {sanitizeGQLAlias} from '../../util/string';
import {splitEscapedString} from '../primitives/splitEscapedString';

// LIMIT_ALL_* are only used against local instances
const LIMIT_ALL_PROJECTS = 10000;
const LIMIT_ALL_REPORTS = 10000;
const LIMIT_ALL_ARTIFACTS = 10000;

const LIMIT_ARTIFACTTYPE_ARTIFACTS = 100;
const LIMIT_ARTIFACTTYPE_ARTIFACTVERSIONS = 100;
const LIMIT_ARTIFACT_VERSIONS = 100;
const LIMIT_ENTITY_PROJECTS = 100;
const LIMIT_ORG_ARTIFACTS = 100;
const LIMIT_ORG_PROJECTS = 100;
const LIMIT_ORG_REPORTS = 100;
const LIMIT_PROJECT_REPORTS = 100;
const LIMIT_PROJECT_ARTIFACT_TYPES = 10;
const LIMIT_PROJECT_RUNS = 100;
const LIMIT_REPORT_STARGAZERS = 100;
const LIMIT_USER_RUNS = 100;
const LIMIT_USER_TEAMS = 100;
const LIMIT_RUN_HISTORY_KEYS = 100;

const gqlBasicField = (name: string, args?: Vega3.QueryArg[]) => {
  const field: Vega3.QueryField = {
    name,
    args,
    fields: [],
  };
  return [field];
};

export const gqlArgs = (args: {
  [key: string]: any;
}): Vega3.QueryArg[] | undefined => {
  if (Object.keys(args).length === 0) {
    return undefined;
  }
  return _.map(args, (v, key) => ({name: key, value: v}));
};

export const gqlObjectField = (
  forwardGraph: ForwardGraph,
  forwardOp: ForwardOp,
  name: string,
  args?: Vega3.QueryArg[],
  opts?: {
    extraFields?: Vega3.QueryField[];
    alias?: string;
  }
) => {
  const extraFields = opts?.extraFields ?? [];
  const alias = opts?.alias;
  const field: Vega3.QueryField = {
    name,
    args,
    fields: [
      {name: 'id', fields: []},
      ...gqlObjectSubfields(forwardGraph, forwardOp),
      ...(extraFields ?? []),
    ],
    alias,
  };
  return field;
};

const getSubfieldOps = (forwardOp: ForwardOp): ForwardOp[] => {
  return [
    ...Array.from(forwardOp.outputNode.inputTo),
    ...Array.from(forwardOp.outputNode.consumedAsTagBy).flatMap(getSubfieldOps),
  ];
};

const gqlObjectSubfields = (
  forwardGraph: ForwardGraph,
  forwardOp: ForwardOp
): Vega3.QueryField[] => {
  return [
    ...getSubfieldOps(forwardOp).flatMap(inputToForwardOp => {
      if (inputToForwardOp.op.name === 'dict') {
        // Very specific support of opDict followed by opPick. The fact that
        // we need something like this is a sign that we need more bookkeeping.
        return gqlObjectSubfieldsForDict(
          forwardGraph,
          forwardOp,
          inputToForwardOp
        );
      } else {
        return toGqlField(forwardGraph, inputToForwardOp);
      }
    }),
  ];
};

const gqlObjectSubfieldsForDict = (
  forwardGraph: ForwardGraph,
  forwardOp: ForwardOp,
  inputToForwardDictOp: ForwardOp
): Vega3.QueryField[] => {
  if (inputToForwardDictOp.op.name !== 'dict') {
    throw new Error(
      `Expected 'dict' op, found ${inputToForwardDictOp.op.name}`
    );
  }
  return [
    ...getSubfieldOps(inputToForwardDictOp).flatMap(dictOpInputToForwardOp => {
      if (dictOpInputToForwardOp.op.name === 'pick') {
        const inputKeyNode = dictOpInputToForwardOp.op.inputs.key;
        if (
          inputKeyNode.nodeType === 'const' &&
          inputKeyNode.type === 'string'
        ) {
          const inputNode =
            inputToForwardDictOp.op.inputs[
              splitEscapedString(inputKeyNode.val).join('.')
            ];
          if (inputNode != null && inputNode.nodeType === 'output') {
            const inputOp = forwardGraph.getOp(inputNode.fromOp);
            if (
              inputOp != null &&
              (inputOp === forwardOp ||
                inputOp.outputNode.consumesTagFrom.has(forwardOp))
            ) {
              return gqlObjectSubfields(forwardGraph, dictOpInputToForwardOp);
            }
          }
        }
      }
      return [];
    }),
  ];
};

const forwardOpHasVarInputOfName = (name: string) => (forwardOp: ForwardOp) =>
  Object.values(forwardOp.op.inputs).some(
    v => v.nodeType === 'var' && v.varName === name
  );

export const toGqlField = (
  forwardGraph: ForwardGraph,
  forwardOp: ForwardOp
): Vega3.QueryField[] => {
  // If the node is invalid, don't continue to traverse it.
  // This happens when users construct invalid graphs. for example:
  // run.tableRows is a valid graph, but not a valid node. This therefore
  // prevents incorrect GQL fields from slipping in.
  if (forwardOp.outputNode.node.type === 'invalid') {
    return [];
  }

  const opInputs = forwardOpInputs(forwardGraph, forwardOp);

  // Find a limit from immediate opLimit child, otherwise use default
  function childLimitWithDefault(defLimit: number): number {
    for (const node of forwardOp.outputNode.inputTo.values()) {
      if (node.op.name === 'limit') {
        const limitOpInputs = forwardOpInputs(forwardGraph, node);
        return limitOpInputs.limit;
      }
    }
    // console.warn(
    //   `Using default limit ${defLimit} for op ${forwardOp.op.name}!`
    // );
    return defLimit;
  }

  if (forwardOp.op.name === 'map') {
    // Walk the mapFn forward to find potential graphql fields
    const argFn = opInputs.mapFn;
    const argFnForwardGraph = newRefForwardGraph();
    argFnForwardGraph.update(argFn);
    const roots = Array.from(argFnForwardGraph.getRoots()).filter(
      forwardOpHasVarInputOfName('row')
    );
    const allFields = roots.map(root => toGqlField(argFnForwardGraph, root));
    const res = _.concat(allFields[0], ...allFields.slice(1));
    return res
      .concat(gqlObjectSubfields(forwardGraph, forwardOp))
      .filter(f => f != null);
  } else if (forwardOp.op.name === 'groupby') {
    // TODO: duplicated from map case above
    const argFn = opInputs.groupByFn;
    const argFnForwardGraph = newRefForwardGraph();
    argFnForwardGraph.update(argFn);
    const roots = Array.from(argFnForwardGraph.getRoots()).filter(
      forwardOpHasVarInputOfName('row')
    );
    const allFields = roots.map(root => toGqlField(argFnForwardGraph, root));
    const res = _.concat(allFields[0], ...allFields.slice(1));
    return res
      .concat(gqlObjectSubfields(forwardGraph, forwardOp))
      .filter(f => f != null);
  } else if (forwardOp.op.name === 'filter') {
    // TODO: duplicated from map case above
    const argFn = opInputs.filterFn;
    const argFnForwardgraph = newRefForwardGraph();
    argFnForwardgraph.update(argFn);
    const roots = Array.from(argFnForwardgraph.getRoots()).filter(
      forwardOpHasVarInputOfName('row')
    );
    const allFields = roots.map(root => toGqlField(argFnForwardgraph, root));
    const res = _.concat(allFields[0], ...allFields.slice(1));
    return res
      .concat(gqlObjectSubfields(forwardGraph, forwardOp))
      .filter(f => f != null);
  } else if (forwardOp.op.name === 'sort') {
    // TODO: duplicated from map case above
    const argFn = opInputs.compFn;
    const argFnForwardgraph = newRefForwardGraph();
    argFnForwardgraph.update(argFn);
    const roots = Array.from(argFnForwardgraph.getRoots()).filter(
      forwardOpHasVarInputOfName('row')
    );
    const allFields = roots.map(root => toGqlField(argFnForwardgraph, root));
    const res = _.concat(allFields[0], ...allFields.slice(1));
    return res
      .concat(gqlObjectSubfields(forwardGraph, forwardOp))
      .filter(f => f != null);
  } else if (
    forwardOp.op.name === 'offset' ||
    forwardOp.op.name === 'limit' ||
    forwardOp.op.name === 'index' ||
    forwardOp.op.name === 'concat' ||
    forwardOp.op.name === 'contains' ||
    forwardOp.op.name === 'list' ||
    forwardOp.op.name === 'concat' ||
    forwardOp.op.name === 'flatten' ||
    forwardOp.op.name === 'dropna' ||
    forwardOp.op.name === 'list-createIndexCheckpointTag'
  ) {
    return gqlObjectSubfields(forwardGraph, forwardOp);
  } else if (forwardOp.op.name === 'dict') {
    // Dict is a special case, and is handled in `gqlObjectSubfields`. Specifically,
    // we need to follow the correct key for the next op.
  } else if (forwardOp.op.name === 'root-entity') {
    const alias = `entity_${hash(opInputs.entityName)}`;
    return [
      gqlObjectField(
        forwardGraph,
        forwardOp,
        'entity',
        gqlArgs({
          name: opInputs.entityName,
        }),
        {alias}
      ),
    ];
  } else if (forwardOp.op.name === 'root-project') {
    const alias = `project_${hash(
      opInputs.entityName + '/' + opInputs.projectName
    )}`;
    return [
      gqlObjectField(
        forwardGraph,
        forwardOp,
        'project',
        gqlArgs({
          entityName: opInputs.entityName,
          name: opInputs.projectName,
        }),
        {alias}
      ),
    ];
  } else if (forwardOp.op.name === 'root-artifactVersion') {
    const projectAlias = `project_${hash(
      opInputs.entityName + '/' + opInputs.projectName
    )}`;
    const artifactTypeAlias = `artifactType_${hash(opInputs.artifactTypeName)}`;
    const artifactAlias = `artifact_${hash(opInputs.artifactVersionName)}`;
    return [
      {
        alias: projectAlias,
        name: 'project',
        args: gqlArgs({
          entityName: opInputs.entityName,
          name: opInputs.projectName,
        }),
        fields: [
          {name: 'id', fields: []},
          {
            alias: artifactTypeAlias,
            name: 'artifactType',
            args: gqlArgs({name: opInputs.artifactTypeName}),
            fields: [
              {name: 'id', fields: []},
              gqlObjectField(
                forwardGraph,
                forwardOp,
                'artifact',
                gqlArgs({name: opInputs.artifactVersionName}),
                {alias: artifactAlias}
              ),
            ],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'root-org') {
    const alias = `organization_${hash(opInputs.orgName)}`;
    return [
      gqlObjectField(
        forwardGraph,
        forwardOp,
        'organization',
        gqlArgs({
          name: opInputs.orgName,
        }),
        {alias}
      ),
    ];
  } else if (forwardOp.op.name === 'root-user') {
    const alias = `user_${hash(opInputs.userName)}`;
    return [
      gqlObjectField(
        forwardGraph,
        forwardOp,
        'user',
        gqlArgs({
          userName: opInputs.userName,
        }),
        {alias}
      ),
    ];
  } else if (forwardOp.op.name === 'root-viewer') {
    // TODO(np): Get rid of this
    return [gqlObjectField(forwardGraph, forwardOp, 'viewer')];
  } else if (forwardOp.op.name === 'root-allProjects') {
    return [
      {
        name: 'instance',
        args: gqlArgs({}),
        fields: [
          {
            name: 'projects',
            args: gqlArgs({
              first: childLimitWithDefault(LIMIT_ALL_PROJECTS),
            }),
            fields: [
              {
                name: 'edges',
                fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
              },
            ],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'root-allReports') {
    return [
      {
        name: 'instance',
        args: gqlArgs({}),
        fields: [
          {
            name: 'views',
            // TODO: hardcoding for perf during dev
            args: gqlArgs({first: childLimitWithDefault(LIMIT_ALL_REPORTS)}),
            fields: [
              {
                name: 'edges',
                fields: [
                  gqlObjectField(forwardGraph, forwardOp, 'node', gqlArgs({}), {
                    extraFields: gqlBasicField('type'),
                  }),
                ],
              },
            ],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'root-allArtifacts') {
    return [
      {
        name: 'instance',
        args: gqlArgs({}),
        fields: [
          {
            name: 'artifactSequences',
            // TODO: hardcoding for perf during dev
            args: gqlArgs({first: childLimitWithDefault(LIMIT_ALL_ARTIFACTS)}),
            fields: [
              {
                name: 'edges',
                fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
              },
            ],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'root-allEntities') {
    return [
      {
        name: 'instance',
        args: gqlArgs({}),
        fields: [gqlObjectField(forwardGraph, forwardOp, 'entities')],
      },
    ];
  } else if (forwardOp.op.name.includes('rpt_')) {
    const alias = `repoInsights_${hash(opInputs.repoName)}_${hash(
      forwardOp.op.name
    )}`;
    return [
      {
        alias,
        name: 'repoInsightsPlotData',
        args: gqlArgs({
          plotName: forwardOp.op.name,
          repoName: opInputs.repoName,
          first: 100000, // todo(dg): actually page this
        }),
        fields: [
          {
            name: 'edges',
            fields: [
              {
                name: 'node',
                fields: [
                  {
                    name: 'row',
                    fields: [],
                  },
                ],
              },
            ],
          },
          {
            name: 'schema',
            fields: [],
          },
          {
            name: 'isNormalizedUserCount',
            fields: [],
          },
        ],
      },
    ];
  } else if (
    forwardOp.op.name === 'entity-name' ||
    forwardOp.op.name === 'entity-link'
  ) {
    return gqlBasicField('name');
  } else if (forwardOp.op.name === 'entity-isTeam') {
    return gqlBasicField('isTeam');
  } else if (forwardGraph.getOp.name === 'entity-internalId') {
    return gqlBasicField('id');
  } else if (forwardOp.op.name === 'entity-portfolios') {
    return [
      {
        name: 'artifactCollections(collectionTypes: [PORTFOLIO])',
        args: [],
        fields: [
          {
            name: 'edges',
            fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
          },
        ],
        alias: 'entityPortfolios',
      },
    ];
  } else if (forwardOp.op.name === 'entity-projects') {
    return [
      {
        name: 'projects',
        // TODO: hardcoding for perf during dev
        args: gqlArgs({
          first: childLimitWithDefault(LIMIT_ENTITY_PROJECTS),
        }),
        fields: [
          {
            name: 'edges',
            fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'entity-reports') {
    return [
      {
        name: 'views',
        // TODO: hardcoding for perf during dev
        args: gqlArgs({
          first: childLimitWithDefault(LIMIT_ORG_REPORTS),
        }),
        fields: [
          {
            name: 'edges',
            fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'entity-org') {
    return [gqlObjectField(forwardGraph, forwardOp, 'organization')];
  } else if (forwardOp.op.name === 'entity-artifactTTLDurationSeconds') {
    return gqlBasicField('artifactTTLDurationSeconds');
  } else if (forwardOp.op.name === 'project-id') {
    return gqlBasicField('id');
  } else if (forwardOp.op.name === 'project-entity') {
    return [gqlObjectField(forwardGraph, forwardOp, 'entity')];
  } else if (forwardOp.op.name === 'project-createdAt') {
    return gqlBasicField('createdAt');
  } else if (forwardOp.op.name === 'project-updatedAt') {
    return gqlBasicField('updatedAt');
  } else if (forwardOp.op.name === 'project-name') {
    return gqlBasicField('name');
  } else if (forwardOp.op.name === 'project-link') {
    return gqlBasicField('name').concat(gqlBasicField('entityName'));
  } else if (forwardOp.op.name === 'project-runs') {
    return [
      {
        name: 'runs',
        // TODO: hardcoding for perf during dev
        // Maybe need to alias this for different limit values
        args: gqlArgs({first: childLimitWithDefault(LIMIT_PROJECT_RUNS)}),
        fields: [
          {
            name: 'edges',
            fields: [
              gqlObjectField(forwardGraph, forwardOp, 'node', undefined, {
                extraFields: [{name: 'name', fields: []}],
              }),
            ],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'project-runQueues') {
    return [gqlObjectField(forwardGraph, forwardOp, 'runQueues')];
  } else if (forwardOp.op.name === 'project-filteredRuns') {
    // We may have multiple of these, each with different `filter`
    // args.  Since we can't be sure that we can merge this runset
    // and rely on a downstream `opFilter` to filter down to each
    // desired subset, need to keep each instance separate by
    // using a suffixed alias.  This must be kept in sync with the resolver
    const alias = `filteredRuns_${hash(opInputs.filter)}`;
    return [
      {
        alias,
        name: 'runs',
        args: gqlArgs({
          first: childLimitWithDefault(LIMIT_PROJECT_RUNS),
          filters: opInputs.filter,
          order: opInputs.order ?? undefined,
        }),
        fields: [
          {
            name: 'edges',
            fields: [
              gqlObjectField(forwardGraph, forwardOp, 'node', undefined, {
                extraFields: [{name: 'name', fields: []}],
              }),
            ],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'project-run') {
    const name = forwardOpInputs(forwardGraph, forwardOp).runName;
    const alias = `run_${hash(name)}`;
    return [
      gqlObjectField(
        forwardGraph,
        forwardOp,
        'run',
        gqlArgs({name}),
        // TODO: make a more generic way of fetching fields required by
        // ops farther down the chain, especially when they use tags. For
        // now, hard coding.
        {
          alias,
          extraFields: [{name: 'name', fields: []}],
        }
      ),
    ];
  } else if (forwardOp.op.name === 'project-artifactTypes') {
    return [
      {
        name: 'artifactTypes',
        // TODO: hardcoding for perf during dev
        args: gqlArgs({
          first: childLimitWithDefault(LIMIT_PROJECT_ARTIFACT_TYPES),
        }),
        fields: [
          {
            name: 'edges',
            fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'project-artifactType') {
    const artifactType = forwardOpInputs(forwardGraph, forwardOp).artifactType;
    const alias = `artifactType_${hash(artifactType)}`;
    return [
      gqlObjectField(
        forwardGraph,
        forwardOp,
        'artifactType',
        gqlArgs({name: artifactType}),
        {alias}
      ),
    ];
  } else if (forwardOp.op.name === 'project-artifact') {
    const artifactName = forwardOpInputs(forwardGraph, forwardOp).artifactName;
    const alias = `artifactCollection_${hash(artifactName)}`;
    return [
      gqlObjectField(
        forwardGraph,
        forwardOp,
        'artifactCollection',
        gqlArgs({name: artifactName}),
        {alias}
      ),
    ];
  } else if (forwardOp.op.name === 'project-artifactVersion') {
    const artifactName = forwardOpInputs(forwardGraph, forwardOp).artifactName;
    const artifactVersionAlias = forwardOpInputs(
      forwardGraph,
      forwardOp
    ).artifactVersionAlias;
    const fullName = artifactName + ':' + artifactVersionAlias;
    const alias = `artifact_${hash(fullName)}`;
    return [
      gqlObjectField(
        forwardGraph,
        forwardOp,
        'artifact',
        gqlArgs({name: fullName}),
        {alias}
      ),
    ];
  } else if (forwardOp.op.name === 'project-reports') {
    return [
      {
        name: 'allViews',
        args: gqlArgs({
          viewType: 'runs',
          first: childLimitWithDefault(LIMIT_PROJECT_REPORTS),
        }),
        fields: [
          {
            name: 'edges',
            fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'project-artifacts') {
    return [
      {
        name: 'artifactCollections',
        fields: [
          {
            name: 'edges',
            fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'runQueue-name') {
    return gqlBasicField('name');
  } else if (forwardOp.op.name === 'org-artifacts') {
    return [
      {
        name: 'artifactCollections',
        // TODO: hardcoding for perf during dev
        args: gqlArgs({first: childLimitWithDefault(LIMIT_ORG_ARTIFACTS)}),
        fields: [
          {
            name: 'edges',
            fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'org-name') {
    return gqlBasicField('name');
  } else if (forwardOp.op.name === 'org-teams') {
    return [gqlObjectField(forwardGraph, forwardOp, 'teams')];
  } else if (forwardOp.op.name === 'report-internalId') {
    return gqlBasicField('id');
  } else if (forwardOp.op.name === 'report-name') {
    return gqlBasicField('displayName');
  } else if (forwardOp.op.name === 'report-link') {
    return gqlBasicField('displayName')
      .concat(gqlBasicField('id'))
      .concat([
        gqlObjectField(forwardGraph, forwardOp, 'project', gqlArgs({}), {
          extraFields: gqlBasicField('entityName').concat(
            gqlBasicField('name')
          ),
        }),
      ]);
  } else if (forwardOp.op.name === 'report-description') {
    return gqlBasicField('description');
  } else if (forwardOp.op.name === 'report-createdAt') {
    return gqlBasicField('createdAt');
  } else if (forwardOp.op.name === 'report-updatedAt') {
    return gqlBasicField('updatedAt');
  } else if (forwardOp.op.name === 'report-project') {
    return [gqlObjectField(forwardGraph, forwardOp, 'project')];
  } else if (forwardOp.op.name === 'report-creator') {
    return [gqlObjectField(forwardGraph, forwardOp, 'user')];
  } else if (forwardOp.op.name === 'report-viewcount') {
    return gqlBasicField('viewCount');
  } else if (forwardOp.op.name === 'report-stargazers') {
    return [
      {
        name: 'stargazers',
        // TODO: hardcoding for perf during dev
        args: gqlArgs({
          first: childLimitWithDefault(LIMIT_REPORT_STARGAZERS),
        }),
        fields: [
          {
            name: 'edges',
            fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'org-members') {
    return [
      {
        name: 'members',
        fields: [gqlObjectField(forwardGraph, forwardOp, 'user')],
      },
    ];
  } else if (forwardOp.op.name === 'org-reports') {
    return [
      {
        name: 'views',
        // TODO: hardcoding for perf during dev
        args: gqlArgs({first: childLimitWithDefault(LIMIT_ORG_REPORTS)}),
        fields: [
          {
            name: 'edges',
            fields: [
              gqlObjectField(forwardGraph, forwardOp, 'node', gqlArgs({}), {
                extraFields: gqlBasicField('type'),
              }),
            ],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'org-projects') {
    return [
      {
        name: 'projects',
        // TODO: hardcoding for perf during dev
        args: gqlArgs({first: childLimitWithDefault(LIMIT_ORG_PROJECTS)}),
        fields: [
          {
            name: 'edges',
            fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'user-runs') {
    return [
      {
        name: 'runs',
        // TODO: hardcoding for perf during dev
        args: gqlArgs({first: childLimitWithDefault(LIMIT_USER_RUNS)}),
        fields: [
          {
            name: 'edges',
            fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'user-entities') {
    return [
      {
        name: 'teams',
        // TODO: hardcoding for perf during dev
        args: gqlArgs({first: childLimitWithDefault(LIMIT_USER_TEAMS)}),
        fields: [
          {
            name: 'edges',
            fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'user-username') {
    return gqlBasicField('username');
  } else if (forwardOp.op.name === 'user-name') {
    return gqlBasicField('name');
  } else if (forwardOp.op.name === 'user-email') {
    return gqlBasicField('email');
  } else if (forwardOp.op.name === 'user-link') {
    return gqlBasicField('name').concat(gqlBasicField('username'));
  } else if (forwardOp.op.name === 'artifact-type') {
    return [gqlObjectField(forwardGraph, forwardOp, 'defaultArtifactType')];
  } else if (forwardOp.op.name === 'artifact-rawTags') {
    return [
      {
        name: 'tags',
        fields: [
          {
            name: 'edges',
            fields: [
              {
                name: 'node',
                fields: gqlBasicField('id')
                  .concat(gqlBasicField('name'))
                  .concat(gqlBasicField('tagCategoryName'))
                  .concat(gqlBasicField('attributes')),
              },
            ],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'artifact-versions') {
    return [
      {
        name: 'artifacts',
        // TODO: hardcoding for perf during dev
        // TODO: we really need to look down the tree to determine the range to select.
        args: gqlArgs({first: childLimitWithDefault(LIMIT_ARTIFACT_VERSIONS)}),
        fields: [
          {
            name: 'edges',
            fields: [
              {
                name: 'version',
                fields: [],
              },
              gqlObjectField(forwardGraph, forwardOp, 'node'),
            ],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'artifact-name') {
    return gqlBasicField('name');
  } else if (forwardOp.op.name === 'artifact-aliases') {
    return [
      {
        name: 'aliases',
        fields: [
          {
            name: 'edges',
            fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'artifact-createdAt') {
    return gqlBasicField('createdAt');
  } else if (forwardOp.op.name === 'artifact-description') {
    return gqlBasicField('description');
  } else if (forwardOp.op.name === 'artifact-project') {
    return [gqlObjectField(forwardGraph, forwardOp, 'project')];
  } else if (forwardOp.op.name === 'artifact-link') {
    return [
      // TODO (ts): Make this a direct GQL edge.
      {
        name: 'defaultArtifactType',
        fields: gqlBasicField('id').concat([{name: 'name', fields: []}]),
      },
      {name: 'name', fields: []},
      {
        name: 'project',
        fields: gqlBasicField('id').concat([
          {name: 'name', fields: []},
          {
            name: 'entity',
            fields: gqlBasicField('id').concat([{name: 'name', fields: []}]),
          },
        ]),
      },
    ];
    // TODO: Provide some sanity here - this is a hidden op right now used
    // in a component which is not surfaced yet.
  } else if (forwardOp.op.name === 'artifactVersion-updateAliasActions') {
    return [
      {
        name: 'artifactActions',
        args: gqlArgs({}),
        fields: [
          {
            name: 'edges',
            fields: [
              {
                name: 'node',
                args: [],
                fields: [
                  gqlObjectField(
                    forwardGraph,
                    forwardOp,
                    '... on UpdateArtifactAction',
                    gqlArgs({}),
                    {
                      extraFields: [
                        gqlBasicField('id')[0],
                        gqlBasicField('createdAt')[0],
                        {
                          name: 'initiator',
                          args: [],
                          fields: [
                            {
                              name: '... on User',
                              args: [],
                              fields: [
                                gqlBasicField('id')[0],
                                gqlBasicField('username')[0],
                              ],
                            },
                            {
                              name: '... on Run',
                              args: [],
                              fields: [
                                gqlBasicField('id')[0],
                                // gqlBasicField('username')[0],
                              ],
                            },
                          ],
                        },
                        {
                          name: 'artifact',
                          args: [],
                          fields: [
                            {
                              name: 'id',
                              args: gqlArgs({}),
                              fields: [],
                            },
                            {
                              name: 'versionIndex',
                              args: gqlArgs({}),
                              fields: [],
                            },
                            {
                              name: 'commitHash',
                              args: gqlArgs({}),
                              fields: [],
                            },
                            {
                              name: 'artifactType',
                              args: gqlArgs({}),
                              fields: [
                                gqlBasicField('id')[0],
                                gqlBasicField('name')[0],
                              ],
                            },
                            {
                              name: 'artifactSequence',
                              args: gqlArgs({}),
                              fields: [
                                gqlBasicField('id')[0],
                                gqlBasicField('name')[0],
                              ].concat([
                                {
                                  name: 'project',
                                  args: gqlArgs({}),
                                  fields: [
                                    gqlBasicField('id')[0],
                                    gqlBasicField('name')[0],
                                  ].concat([
                                    {
                                      name: 'entity',
                                      args: gqlArgs({}),
                                      fields: [
                                        gqlBasicField('id')[0],
                                        gqlBasicField('name')[0],
                                      ],
                                    },
                                  ]),
                                },
                              ]),
                            },
                          ],
                        },
                        // gqlBasicField('initiator')[0],
                        {
                          name: 'oldAliases',
                          args: [],
                          fields: [
                            gqlBasicField('id')[0],
                            gqlBasicField('alias')[0],
                          ],
                        },
                        {
                          name: 'newAliases',
                          args: [],
                          fields: [
                            gqlBasicField('id')[0],
                            gqlBasicField('alias')[0],
                          ],
                        },
                      ],
                    }
                  ),
                ],
              },
            ],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'artifactType-artifacts') {
    return [
      {
        name: 'artifactCollections',
        // TODO: hardcoding for perf during dev
        args: gqlArgs({
          first: childLimitWithDefault(LIMIT_ARTIFACTTYPE_ARTIFACTS),
        }),
        fields: [
          {
            name: 'edges',
            fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'artifactType-sequences') {
    return [
      {
        name: `artifactCollections(first: ${childLimitWithDefault(
          LIMIT_ARTIFACTTYPE_ARTIFACTS
        )}, collectionTypes: [SEQUENCE])`,
        fields: [
          {
            name: 'edges',
            fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
          },
        ],
        alias: 'artifactSequences',
      },
    ];
  } else if (forwardOp.op.name === 'artifactType-portfolios') {
    return [
      {
        name: `artifactCollections(first: ${childLimitWithDefault(
          LIMIT_ARTIFACTTYPE_ARTIFACTS
        )}, collectionTypes: [PORTFOLIO])`,
        fields: [
          {
            name: 'edges',
            fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
          },
        ],
        alias: 'artifactPortfolios',
      },
    ];
  } else if (forwardOp.op.name === 'artifactType-artifactVersions') {
    return [
      {
        name: 'artifactCollections',
        // TODO: hardcoding for perf during dev
        args: gqlArgs({
          first: childLimitWithDefault(LIMIT_ARTIFACTTYPE_ARTIFACTVERSIONS),
        }),
        fields: [
          {
            name: 'edges',
            fields: [
              {
                name: 'node',
                fields: [
                  {name: 'id', fields: []},
                  {
                    name: 'artifacts',
                    fields: [
                      {
                        name: 'edges',
                        fields: [
                          gqlObjectField(forwardGraph, forwardOp, 'node'),
                        ],
                      },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'artifactType-name') {
    return gqlBasicField('name');
  } else if (forwardOp.op.name === 'artifactVersion-size') {
    return gqlBasicField('size');
  } else if (forwardOp.op.name === 'artifactVersion-state') {
    return gqlBasicField('state');
  } else if (forwardOp.op.name === 'artifactVersion-description') {
    return gqlBasicField('description');
  } else if (forwardOp.op.name === 'artifactVersion-createdAt') {
    return gqlBasicField('createdAt');
  } else if (forwardOp.op.name === 'artifactVersion-referenceCount') {
    return gqlBasicField('usedCount');
  } else if (forwardOp.op.name === 'artifactVersion-historyStep') {
    return gqlBasicField('historyStep');
  } else if (forwardOp.op.name === 'artifactVersion-metadata') {
    return gqlBasicField('metadata');
  } else if (forwardOp.op.name === 'artifactVersion-ttlDurationSeconds') {
    return gqlBasicField('ttlDurationSeconds');
  } else if (forwardOp.op.name === 'artifactVersion-ttlIsInherited') {
    return gqlBasicField('ttlIsInherited');
  } else if (forwardOp.op.name === 'artifactVersion-fileCount') {
    return gqlBasicField('fileCount');
  } else if (forwardOp.op.name === 'artifactVersion-artifactType') {
    return [gqlObjectField(forwardGraph, forwardOp, 'artifactType')];
  } else if (forwardOp.op.name === 'artifactVersion-isGenerated') {
    return gqlBasicField('isGenerated');
  } else if (forwardOp.op.name === 'artifactVersion-isLinkedToGlobalRegistry') {
    return gqlBasicField('isLinkedToGlobalRegistry');
  } else if (forwardOp.op.name === 'artifactVersion-rawTags') {
    return [
      {
        name: 'tags',
        fields: gqlBasicField('id')
          .concat(gqlBasicField('name'))
          .concat(gqlBasicField('tagCategoryName'))
          .concat(gqlBasicField('attributes')),
      },
    ];
  } else if (forwardOp.op.name === 'artifactVersion-artifactCollections') {
    return [
      {
        name: 'artifactCollections',
        fields: [
          {
            name: 'edges',
            fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'artifactVersion-memberships') {
    return [
      {
        name: 'artifactMemberships',
        fields: [
          {
            name: 'edges',
            fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'artifactVersion-createdBy') {
    // This op (and it's sister op artifactVersion-createdByUser)
    // have an interesting characteristic to study.
    // To effectively lookup fields conditioned on type, we need 3 things:
    // 1. To use the `... on Type` operator
    // 2. To use an alias
    // 3. To ensure that all other possible types are still fetched with an ID
    //
    // All in all, good use case to provide info for type-based logic.
    return [
      {
        name: 'createdBy',
        args: gqlArgs({}),
        fields: [
          gqlObjectField(forwardGraph, forwardOp, '... on Run'),
          {name: '... on User', fields: [{name: 'id', fields: []}]},
        ],
        alias: 'createdByRun',
      },
    ];
  } else if (forwardOp.op.name === 'artifactVersion-createdByUser') {
    return [
      {
        name: 'createdBy',
        args: gqlArgs({}),
        fields: [
          gqlObjectField(forwardGraph, forwardOp, '... on User'),
          {name: '... on Run', fields: [{name: 'id', fields: []}]},
        ],
        alias: 'createdByUser',
      },
    ];
  } else if (forwardOp.op.name === 'artifactVersion-digest') {
    return gqlBasicField('digest');
  } else if (forwardOp.op.name === 'artifactVersion-hash') {
    return gqlBasicField('commitHash');
  } else if (forwardOp.op.name === 'artifactVersion-artifactSequence') {
    return [gqlObjectField(forwardGraph, forwardOp, 'artifactSequence')];
  } else if (forwardOp.op.name === 'artifactVersion-link') {
    return [
      {
        name: 'commitHash',
        args: gqlArgs({}),
        fields: [],
      },
      {
        name: 'versionIndex',
        args: gqlArgs({}),
        fields: [],
      },
      {
        name: 'artifactType',
        args: gqlArgs({}),
        fields: gqlBasicField('id').concat([{name: 'name', fields: []}]),
      },
      {
        name: 'artifactSequence',
        args: gqlArgs({}),
        fields: gqlBasicField('id').concat([
          {name: 'name', fields: []},
          {
            name: 'project',
            args: gqlArgs({}),
            fields: gqlBasicField('id').concat([
              {name: 'name', fields: []},
              {
                name: 'entity',
                args: gqlArgs({}),
                fields: gqlBasicField('id').concat([
                  {name: 'name', fields: []},
                ]),
              },
            ]),
          },
        ]),
      },
    ];
  } else if (forwardOp.op.name === 'artifactVersion-aliases') {
    return [
      gqlObjectField(forwardGraph, forwardOp, 'aliases', undefined, {
        extraFields: gqlBasicField('alias'),
      }),
    ];
  } else if (forwardOp.op.name === 'artifactVersion-name') {
    // We want to construct <artifactName>:v<versionIndex>
    return gqlBasicField('versionIndex').concat([
      {
        name: 'aliases',
        args: gqlArgs({}),
        fields: gqlBasicField('id').concat(gqlBasicField('alias')),
      },
      {
        name: 'artifactSequence',
        args: gqlArgs({}),
        fields: gqlBasicField('id').concat(gqlBasicField('name')),
      },
    ]);
  } else if (forwardOp.op.name === 'artifactVersion-versionId') {
    return gqlBasicField('versionIndex');
  } else if (forwardOp.op.name === 'artifactVersion-usedBy') {
    return [
      {
        name: 'usedBy',
        args: gqlArgs({}),
        fields: [
          {
            name: 'edges',
            fields: [
              gqlObjectField(forwardGraph, forwardOp, 'node', gqlArgs({})),
            ],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'artifactAlias-alias') {
    return gqlBasicField('alias');
  } else if (forwardOp.op.name === 'artifactAlias-artifact') {
    return [gqlObjectField(forwardGraph, forwardOp, 'artifactCollection')];
  } else if (forwardOp.op.name === 'run-id') {
    return gqlBasicField('name');
  } else if (forwardOp.op.name === 'run-name') {
    return gqlBasicField('displayName');
  } else if (forwardOp.op.name === 'run-jobType') {
    return gqlBasicField('jobType');
  } else if (forwardOp.op.name === 'run-link') {
    return gqlBasicField('displayName')
      .concat(gqlBasicField('name'))
      .concat([
        gqlObjectField(forwardGraph, forwardOp, 'project', gqlArgs({}), {
          extraFields: gqlBasicField('name').concat(
            gqlBasicField('entityName')
          ),
        }),
      ]);
  } else if (forwardOp.op.name === 'run-user') {
    return [gqlObjectField(forwardGraph, forwardOp, 'user')];
  } else if (forwardOp.op.name === 'run-createdAt') {
    return gqlBasicField('createdAt');
  } else if (forwardOp.op.name === 'run-updatedAt') {
    return gqlBasicField('updatedAt');
  } else if (forwardOp.op.name === 'run-heartbeatAt') {
    return gqlBasicField('heartbeatAt');
  } else if (forwardOp.op.name === 'run-project') {
    return [gqlObjectField(forwardGraph, forwardOp, 'project')];
  } else if (forwardOp.op.name === 'run-jobtype') {
    return gqlBasicField('jobType');
  } else if (forwardOp.op.name === 'run-loggedArtifactVersion') {
    // TODO: we should recurse here instead of hard coding the fields we want!
    // (like run-loggedArtifacts)
    return [
      {
        name: 'outputArtifacts',
        args: gqlArgs({}),
        fields: [
          {
            name: 'edges',
            fields: [
              gqlObjectField(forwardGraph, forwardOp, 'node', gqlArgs({}), {
                extraFields: [
                  gqlBasicField('versionIndex')[0],
                  {
                    name: 'aliases',
                    args: gqlArgs({}),
                    fields: gqlBasicField('id').concat(gqlBasicField('alias')),
                  },
                  {
                    name: 'artifactSequence',
                    args: gqlArgs({}),
                    fields: gqlBasicField('id').concat(gqlBasicField('name')),
                  },
                ],
              }),
            ],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'run-loggedArtifactVersions') {
    return [
      {
        name: 'outputArtifacts',
        args: gqlArgs({}),
        fields: [
          {
            name: 'edges',
            fields: [
              gqlObjectField(forwardGraph, forwardOp, 'node', gqlArgs({})),
            ],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'run-usedArtifactVersions') {
    return [
      {
        name: 'inputArtifacts',
        args: gqlArgs({}),
        fields: [
          {
            name: 'edges',
            fields: [
              gqlObjectField(forwardGraph, forwardOp, 'node', gqlArgs({})),
            ],
          },
        ],
      },
    ];
  } else if (
    forwardOp.op.name === '_run-historykeyinfo' ||
    forwardOp.op.name === 'refine_history_type'
  ) {
    return gqlBasicField('historyKeys');
  } else if (
    forwardOp.op.name === 'run-history' ||
    forwardOp.op.name === 'refine_history_type'
  ) {
    return gqlBasicField('history');
  } else if (forwardOp.op.name === 'run-historyAsOf') {
    const asOfStep = opInputs.asOfStep ?? 0;
    const minStep = asOfStep;
    const maxStep = minStep + 1;
    return [
      {
        name: 'history',
        args: gqlArgs({
          minStep,
          maxStep,
          maxKeyLimit: LIMIT_RUN_HISTORY_KEYS,
        }),
        fields: [],
        alias: `historyAsOf_${opInputs.asOfStep}`,
      },
    ];
  } else if (
    forwardOp.op.name === 'run-summary' ||
    forwardOp.op.name === 'refine_summary_type'
  ) {
    return gqlBasicField('summaryMetrics');
  } else if (forwardOp.op.name === 'run-runtime') {
    return gqlBasicField('computeSeconds');
  } else if (forwardOp.op.name === 'run-config') {
    return gqlBasicField('config');
  } else if (forwardOp.op.name === 'artifactMembership-id') {
    return gqlBasicField('id');
  } else if (forwardOp.op.name === 'artifactMembership-collection') {
    return [gqlObjectField(forwardGraph, forwardOp, 'artifactCollection')];
  } else if (forwardOp.op.name === 'artifactMembership-artifactVersion') {
    return [gqlObjectField(forwardGraph, forwardOp, 'artifact')];
  } else if (forwardOp.op.name === 'artifactMembership-createdAt') {
    return gqlBasicField('createdAt');
  } else if (forwardOp.op.name === 'artifactMembership-commitHash') {
    return gqlBasicField('commitHash');
  } else if (forwardOp.op.name === 'artifactMembership-versionIndex') {
    return gqlBasicField('versionIndex');
  } else if (forwardOp.op.name === 'artifactMembership-aliases') {
    return [
      gqlObjectField(forwardGraph, forwardOp, 'aliases', undefined, {
        extraFields: gqlBasicField('alias'),
      }),
    ];
  } else if (forwardOp.op.name === 'artifactMembership-link') {
    return [
      {name: 'versionIndex', fields: []},
      {
        name: 'artifactCollection',
        fields: gqlBasicField('id').concat([
          {
            name: 'defaultArtifactType',
            fields: gqlBasicField('id').concat([{name: 'name', fields: []}]),
          },
          {name: 'name', fields: []},
          {
            name: 'project',
            fields: gqlBasicField('id').concat([
              {name: 'name', fields: []},
              {
                name: 'entity',
                fields: gqlBasicField('id').concat([
                  {name: 'name', fields: []},
                ]),
              },
            ]),
          },
        ]),
      },
    ];
  } else if (forwardOp.op.name === 'artifact-memberships') {
    return [
      {
        name: 'artifactMemberships',
        fields: [
          {
            name: 'edges',
            fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
          },
        ],
      },
    ];
  } else if (forwardOp.op.name === 'artifact-membershipForAlias') {
    const alias = sanitizeGQLAlias(`artifactMembership_${opInputs.aliasName}`);
    return [
      gqlObjectField(
        forwardGraph,
        forwardOp,
        'artifactMembership',
        gqlArgs({aliasName: opInputs.aliasName}),
        {alias}
      ),
    ];
  } else if (forwardOp.op.name === 'artifact-lastMembership') {
    return [
      {
        alias: 'lastMembership',
        name: 'artifactMemberships',
        args: gqlArgs({first: 1}),
        fields: [
          {
            name: 'edges',
            fields: [gqlObjectField(forwardGraph, forwardOp, 'node')],
          },
        ],
      },
    ];
  } else {
    // console.log(`toGqlField: NOOP for forwardOp '${forwardOp.op.name}'`);
  }
  return [];
};

function mergeArgs(
  fieldName: string,
  prev?: Vega3.QueryArg[],
  incoming?: Vega3.QueryArg[]
): Vega3.QueryArg[] | undefined {
  prev = prev ?? [];
  incoming = incoming ?? [];
  // console.log(
  //   `  merge args for ${fieldName}: prev`,
  //   prev,
  //   'incoming',
  //   incoming
  // );
  if (
    prev?.length !== incoming?.length // Arg sets have different lengths
  ) {
    if (['summaryMetrics', 'config'].includes(fieldName)) {
      // Special case: absence of keys for these fields means "get the whole object"
      return undefined;
    }
    // Can't merge in general case if only one or none provided
    throw new Error(
      `Invalid args merge: Cannot merge ${JSON.stringify(
        prev
      )} and ${JSON.stringify(incoming)}`
    );
  }
  const mergedArgs = new Map<string, Vega3.QueryArg>();
  for (const arg of prev || []) {
    mergedArgs.set(arg.name, arg);
  }
  for (const arg of incoming || []) {
    const seenArg = mergedArgs.get(arg.name);
    if (!seenArg) {
      throw new Error(
        `Invalid args merge: previous args do not have new arg key "${arg.name}" (field = ${fieldName})`
      );
    } else if (arg.name === 'keys') {
      const mergedArg = {
        name: 'keys',
        value: [...new Set([...seenArg.value, ...arg.value])],
      };
      mergedArgs.set('keys', mergedArg);
    } else {
      // TODO(np): Naively take the later value
      console.warn(
        `[CG GraphQL] Naively merging arg "${arg.name}" for field "${fieldName}"`
      );
      mergedArgs.set(arg.name, arg);
    }
  }
  return Array.from(mergedArgs.values());
}

function mergeField(
  prev: Vega3.QueryField,
  incoming: Vega3.QueryField
): Vega3.QueryField {
  if (prev.alias !== incoming.alias) {
    throw new Error(
      `Attempt to merge fields with different aliases: "${prev.alias}" and "${incoming.alias}"`
    );
  }
  if (prev.name !== incoming.name) {
    throw new Error(
      `Attempt to merge fields with different names: "${prev.name}" and "${incoming.name}"`
    );
  }
  return {
    name: incoming.name,
    alias: incoming.alias,
    args: mergeArgs(prev.name, prev.args, incoming.args),
    fields: mergeFields(prev.fields.concat(incoming.fields)),
  };
}

function mergeFields(fields: Vega3.QueryField[]): Vega3.QueryField[] {
  const mergedFields = new Map<string, Vega3.QueryField>();
  for (const nextField of fields) {
    const fieldKey = nextField.alias ?? nextField.name;
    const seenField = mergedFields.get(fieldKey);
    if (!seenField) {
      // First encounter
      nextField.fields = mergeFields(nextField.fields);
      mergedFields.set(fieldKey, nextField);
    } else if (_.isEqual(seenField, nextField)) {
      // Nth encounter, seen field matches next field
      continue;
    } else {
      //  Nth encounter, seen field does not match next field, merge
      mergedFields.set(fieldKey, mergeField(seenField, nextField));
    }
  }
  return Array.from(mergedFields.values());
}

// Wraps toGqlFields to clean up duplicate non-parameterized fields
// and merge parameterized fields
export const toGqlQuery = (
  forwardGraph: ForwardGraph,
  forwardOp: ForwardOp
): Vega3.QueryField[] => {
  const fields = toGqlField(forwardGraph, forwardOp);
  return mergeFields(fields);
};
