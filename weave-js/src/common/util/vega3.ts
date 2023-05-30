import {produce} from 'immer';
import * as _ from 'lodash';
import {VisualizationSpec} from 'react-vega';

import {flatten} from './flatten';
import {deepMapValuesAndArrays, notEmpty} from './obj';
import {UserSettings} from './vega2';

export interface Query {
  queryFields: QueryField[];
}

export interface QueryArg {
  name: string;
  value: any;
}

export interface QueryField {
  name: string;
  args?: QueryArg[];

  // TODO: make fields? optional, it's annoying
  fields: QueryField[];
  alias?: string;
}

export interface QueryTemplateArg {
  typeName: string;
  fieldName: string;
  argName: string;
  value: string;
}

export interface Transform {
  name: 'tableWithFullPathColNames' | 'tableWithLeafColNames';
}

export interface Table {
  cols: string[];
  rows: Array<{[key: string]: any}>;
}

/**
 * For renderer
 */

export interface FieldRef {
  type: 'field' | 'string';
  name: string;
  raw: string;
  default?: string;
}

export const VIEW_ALL_RUNS = 'All runs';

export function updateQueryIndex(query: Query, index: number) {
  const result = produce(query, draft => {
    draft.queryFields
      .find(f => f.name === 'runSets')
      ?.fields.filter(f => f.name === 'historyTable')
      ?.forEach(field => {
        const val = field.args?.find(a => a.name === 'index');
        if (val == null) {
          field.args?.push({name: 'index', value: index});
        } else {
          val.value = index;
        }
      });
  });
  return result;
}

export function getDefaultViewedRun(
  currDefaultRun?: string,
  runSelectorOptions?: string[]
): string {
  if (currDefaultRun && runSelectorOptions) {
    if (runSelectorOptions.find(row => row === currDefaultRun)) {
      return currDefaultRun;
    } else if (runSelectorOptions.length > 1) {
      // we skip the first one which defaults to all the runs
      return runSelectorOptions[1];
    }
  }

  return VIEW_ALL_RUNS;
} /* eslint-disable no-template-curly-in-string */
export const DEFAULT_LIMIT: number = 500;
export const defaultRunSetsQuery: Query = {
  queryFields: [
    {
      name: 'runSets',
      args: [
        {name: 'runSets', value: '${runSets}'},
        {name: 'limit', value: DEFAULT_LIMIT},
      ],
      fields: [
        {name: 'id', fields: []},
        {name: 'name', fields: []},
        {
          name: 'summary',
          args: [{name: 'keys', value: ['']}],
          fields: [],
        },
      ],
    },
  ],
};

function toRef(s: string): FieldRef | null {
  const [refName, rest, dflt] = s.split(':', 3);
  if (rest == null) {
    return null;
  }
  switch (refName) {
    case 'field':
      return {type: 'field', name: rest, raw: s};
    case 'string':
      return {type: 'string', name: rest, default: dflt, raw: s};
    default:
      return null;
  }
}

export function extractRefs(s: string): FieldRef[] {
  const match = s.match(new RegExp(`\\$\\{.*?\\}`, 'g'));
  if (match == null) {
    return [];
  }
  return match
    .map(m => {
      const ref = toRef(m.slice(2, m.length - 1));
      return ref == null ? null : {...ref, raw: m};
    })
    .filter(notEmpty);
}

export function fieldInjectResult(
  ref: FieldRef,
  userSettings: UserSettings
): string | null {
  let result = '';
  switch (ref.type) {
    case 'field':
      result = userSettings.fieldSettings?.[ref.name] || '';
      if (typeof result !== 'string') {
        result = String(result);
      }
      result = result.replace(/\./g, '\\.');
      return result;
    case 'string':
      return userSettings.stringSettings?.[ref.name] || ref.default || '';
    default:
      return null;
  }
}

export function parseSpecFields(spec: VisualizationSpec): FieldRef[] {
  const refs = _.uniqWith(
    _.flatMap(
      _.filter(flatten(spec), v => typeof v === 'string'),
      v => extractRefs(v)
    ),
    _.isEqual
  );
  return refs;
}

export function makeInjectMap(
  refs: FieldRef[],
  userSettings: UserSettings
): Array<{from: string; to: string}> {
  const result: Array<{from: string; to: string}> = [];
  for (const ref of refs) {
    const inject = fieldInjectResult(ref, userSettings);
    if (inject != null) {
      result.push({
        from: ref.raw,
        to: inject,
      });
    }
  }
  return result;
}

export function injectFields(
  spec: VisualizationSpec,
  refs: FieldRef[],
  userSettings: UserSettings
): VisualizationSpec {
  const injectMap = makeInjectMap(refs, userSettings);
  return deepMapValuesAndArrays(spec, (s: any) => {
    if (typeof s === 'string') {
      for (const mapping of injectMap) {
        // Replace all (s.replace only replaces the first occurrence)
        s = s.split(mapping.from).join(mapping.to);
      }
    }
    return s;
  });
}

function hasInput(specBranch: any) {
  if (typeof specBranch === 'object') {
    for (const [key, val] of Object.entries(specBranch)) {
      if (key === 'input') {
        return true;
      }
      if (hasInput(val)) {
        return true;
      }
    }
  }
  return false;
}

export function specHasBindings(spec: VisualizationSpec) {
  if (spec.$schema?.includes('vega-lite/v5')) {
    const params = (spec as any).params;
    return hasInput(params);
  } else if (spec.$schema?.includes('vega-lite')) {
    const selection = (spec as any).selection;
    return hasInput(selection);
  } else {
    const signals = (spec as any).signals;
    if (Array.isArray(signals)) {
      for (const s of signals) {
        if (s.bind != null) {
          return true;
        }
      }
    }
  }
  return false;
}
