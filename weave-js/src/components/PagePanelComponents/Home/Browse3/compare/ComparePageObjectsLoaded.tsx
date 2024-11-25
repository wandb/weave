/**
 * This is the main layout of the compare page.
 * It also handles the logic around ref expansion.
 */
import {GridRowId} from '@mui/x-data-grid-pro';
import {Switch} from '@wandb/weave/components';
import * as DropdownMenu from '@wandb/weave/components/DropdownMenu';
import _ from 'lodash';
import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {Button} from '../../../../Button';
import {Icon} from '../../../../Icon';
import {TailwindContents} from '../../../../Tailwind';
import {isWeaveRef} from '../filters/common';
import {mapObject, TraverseContext} from '../pages/CallPage/traverse';
import {SimplePageLayout} from '../pages/common/SimplePageLayout';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {
  queryGetString,
  querySetArray,
  querySetString,
  queryToggleBoolean,
} from '../urlQueryUtil';
import {computeDiff, mergeObjects} from './compare';
import {CompareGrid, MAX_OBJECT_COLS} from './CompareGrid';
import {isSequentialVersions, parseSpecifier} from './hooks';
import {getExpandableRefs, RefValues, RESOLVED_REF_KEY} from './refUtil';
import {ShoppingCart} from './ShoppingCart';
import {ComparableObject, Mode} from './types';

type ComparePageObjectsLoadedProps = {
  objectType: 'object' | 'call';
  objectIds: string[];
  mode: Mode;
  baselineEnabled: boolean;
  onlyChanged: boolean;
  objects: ComparableObject[];
  lastVersionIndices?: Record<string, number>;
};

// TODO: These are always going to be different so not useful to flag as such.
//       But maybe seeing value for things like versionHash is still useful?
const UNINTERESTING_PATHS_CALL = ['id'];
const UNINTERESTING_PATHS_OBJ = [
  'baseObjectClass',
  'entity',
  'path',
  'objectId',
  'project',
  'scheme',
  'versionHash',
  'versionIndex',
  'weaveKind',
];

const IconPlaceholder = () => <div className="h-18 w-18" />;

export const ComparePageObjectsLoaded = ({
  objectType,
  objectIds,
  mode,
  baselineEnabled,
  onlyChanged,
  objects,
  lastVersionIndices,
}: ComparePageObjectsLoadedProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [expandedIds, setExpandedIds] = useState<GridRowId[]>([]);

  // Sequential object version navigation
  // TODO: Handle deleted versions
  // TODO: Disable when at last version to avoid crash
  const param = objectType === 'call' ? 'call' : 'obj';
  let isSequential = false;
  const first = parseSpecifier(objectIds[0]);
  const last = parseSpecifier(objectIds[objectIds.length - 1]);
  let onPrev: (() => void) | undefined;
  let onNext: (() => void) | undefined;
  if (objectType === 'object') {
    isSequential = isSequentialVersions(objectIds);
    const onNav = (delta: number) => {
      const specifiers = [];
      for (let i = 0; i < objectIds.length; i++) {
        specifiers.push(`${first.name}:v${first.version! + i + delta}`);
      }
      querySetArray(history, param, specifiers);
    };
    onPrev = () => onNav(-1);
    onNext = () => onNav(1);
  }

  const history = useHistory();

  // TODO: For efficiency we might move this logic up to the
  //       initial data fetching layer.
  const selected = queryGetString(history, 'sel');
  let filteredObjectIds = objectIds;
  let filteredObjects = objects;
  if (selected) {
    const idx = objectIds.indexOf(selected);
    if (idx === 0) {
      filteredObjectIds = [objectIds[0], objectIds[1]];
      filteredObjects = [objects[0], objects[1]];
    } else if (idx > 0) {
      if (baselineEnabled) {
        filteredObjectIds = [objectIds[0], objectIds[idx]];
        filteredObjects = [objects[0], objects[idx]];
      } else {
        filteredObjectIds = [objectIds[idx - 1], objectIds[idx]];
        filteredObjects = [objects[idx - 1], objects[idx]];
      }
    }
  }

  const {useRefsData} = useWFHooks();

  // `resolvedData` holds ref-resolved data.
  const [resolvedData, setResolvedData] = useState<ComparableObject[]>(objects);

  // `dataRefs` are the refs contained in the data, filtered to only include expandable refs.
  const dataRefs = useMemo(() => getExpandableRefs(objects), [objects]);

  // Expanded refs are the explicit set of refs that have been expanded by the user. Note that
  // this might contain nested refs not in the `dataRefs` set. The keys are object paths at which the refs were expanded
  // and the values are the corresponding ref strings.
  const [expandedRefs, setExpandedRefs] = useState<{[path: string]: string[]}>(
    {}
  );

  // `addExpandedRefs` is a function that can be used to add expanded refs to the `expandedRefs` state.
  const addExpandedRefs = useCallback((path: string, refsToAdd: string[]) => {
    setExpandedRefs(eRefs => ({...eRefs, [path]: refsToAdd}));
  }, []);

  // `refs` is the union of `dataRefs` and the refs in `expandedRefs`.
  const refs = useMemo(() => {
    return Array.from(
      new Set([...dataRefs, ...Object.values(expandedRefs).flat()])
    );
  }, [dataRefs, expandedRefs]);

  // finally, we get the ref data for all refs. This function is highly memoized and
  // cached. Therefore, we only ever make network calls for new refs in the list.
  const refsData = useRefsData(refs);

  // This effect is responsible for resolving the refs in the data. It iteratively
  // replaces refs with their resolved values. It also adds a `_ref` key to the resolved
  // value to indicate the original ref URI. It is ultimately responsible for setting
  // `resolvedData`.
  useEffect(() => {
    if (refsData.loading) {
      return;
    }
    const resolvedRefData = refsData.result;

    const refValues: RefValues = {};
    for (const [r, v] of _.zip(refs, resolvedRefData)) {
      if (!r || !v) {
        // Shouldn't be possible
        continue;
      }
      let val = r;
      if (v == null) {
        console.error('Error resolving ref', r);
      } else {
        val = v;
        if (typeof val === 'object' && val !== null) {
          val = {
            ...v,
            [RESOLVED_REF_KEY]: r,
          };
        } else {
          // This makes it so that runs pointing to primitives can still be expanded in the table.
          val = {
            '': v,
            [RESOLVED_REF_KEY]: r,
          };
        }
      }
      refValues[r] = val;
    }
    let resolved = objects;
    let dirty = true;
    const mapper = (context: TraverseContext) => {
      if (
        isWeaveRef(context.value) &&
        refValues[context.value] != null &&
        // Don't expand _ref keys
        context.path.tail() !== RESOLVED_REF_KEY
      ) {
        dirty = true;
        return refValues[context.value];
      }
      return _.clone(context.value);
    };
    while (dirty) {
      dirty = false;
      resolved = resolved.map(o => mapObject(o, mapper));
    }
    setResolvedData(resolved);
  }, [objects, refs, refsData.loading, refsData.result]);

  const merged = mergeObjects(objectIds, resolvedData);

  // Hide rows that are uninteresting for diff
  const uninterestingPaths =
    objectType === 'call' ? UNINTERESTING_PATHS_CALL : UNINTERESTING_PATHS_OBJ;
  const filtered = merged.filter(
    row => !uninterestingPaths.includes(row.path.toString())
  );
  const diffed = computeDiff(objectIds, filtered, false);

  // Determine if objects are all the same type. If so, use that
  // term instead of the generic "object" in title
  let title = 'Compare calls';
  if (objectType === 'object') {
    const baseClasses = objects.map(v => v.baseObjectClass);
    const allSameType =
      baseClasses[0] && baseClasses.every(c => c === baseClasses[0]);
    const baseType = allSameType
      ? baseClasses[0]?.toLocaleLowerCase()
      : 'object';
    title = `Compare ${baseType}s`;
  }

  const hasModes = objectIds.length === 2 || selected;
  const checkedMode = hasModes ? mode : 'parallel';

  const cartItems = objects.map(v => {
    if (objectType === 'call') {
      return {
        key: 'call',
        value: v.id,
        label: v.id.slice(-4),
      };
    }
    return {
      key: 'obj',
      value: `${v.objectId}:v${v.versionIndex}`,
    };
  });

  const onSetMode = (newMode: Mode) => {
    querySetString(history, 'mode', newMode);
  };

  const setOnlyChanged = () => {
    queryToggleBoolean(history, 'changed', false);
  };

  const onSetBaseline = (value: boolean) => {
    const {search} = history.location;
    const params = new URLSearchParams(search);
    if (value) {
      params.set('baseline', '1');
    } else {
      params.delete('baseline');
    }
    history.replace({
      search: params.toString(),
    });
  };

  const tooManyCols = objectIds.length > MAX_OBJECT_COLS && !selected;

  return (
    <SimplePageLayout
      title={title}
      hideTabsIfSingle
      tabs={[
        {
          label: '',
          content: (
            <TailwindContents>
              <div className="flex items-center gap-4 px-16 pt-12">
                {isSequential && (
                  <Button
                    size="small"
                    disabled={first.version === 0}
                    icon="back"
                    variant="ghost"
                    onClick={onPrev}
                    tooltip="Decrement the selected versions of this object to view earlier changes"
                  />
                )}
                <ShoppingCart
                  items={cartItems}
                  baselineEnabled={baselineEnabled}
                  selected={selected}
                />
                {isSequential && (
                  <Button
                    size="small"
                    disabled={
                      lastVersionIndices &&
                      last.version === lastVersionIndices[last.name]
                    }
                    icon="forward-next"
                    variant="ghost"
                    onClick={onNext}
                    tooltip="Increment the selected versions of this object to view later changes"
                  />
                )}
              </div>
              <div className="flex items-center gap-16 px-16 py-16">
                <div className="flex h-28 items-center gap-4">
                  <Switch.Root
                    id="diffChangeSwitch"
                    size="small"
                    checked={onlyChanged}
                    onCheckedChange={setOnlyChanged}>
                    <Switch.Thumb size="small" checked={onlyChanged} />
                  </Switch.Root>
                  <label
                    className="cursor-pointer select-none"
                    htmlFor="diffChangeSwitch">
                    Diff only
                  </label>
                </div>
                {hasModes && (
                  <div>
                    <Button
                      size="small"
                      icon="split"
                      variant="secondary"
                      onClick={() => onSetMode('parallel')}
                      active={checkedMode === 'parallel'}
                      tooltip="Show double column view">
                      Side-by-side
                    </Button>
                    <Button
                      size="small"
                      icon="content-full-width"
                      variant="secondary"
                      onClick={() => onSetMode('unified')}
                      active={checkedMode === 'unified'}
                      tooltip="Show single column view">
                      Unified
                    </Button>
                  </div>
                )}
                {tooManyCols && (
                  <div>Viewing first {MAX_OBJECT_COLS} columns only</div>
                )}
                <div className="flex-grow" />
                {objectIds.length > 2 && (
                  <DropdownMenu.Root open={isOpen} onOpenChange={setIsOpen}>
                    <DropdownMenu.Trigger>
                      <div className="cursor-pointer">
                        <div className="flex items-center gap-10">
                          {baselineEnabled
                            ? 'Compare with baseline'
                            : 'Compare with previous'}{' '}
                          <Icon name="chevron-down" />
                        </div>
                      </div>
                    </DropdownMenu.Trigger>
                    <DropdownMenu.Portal>
                      <DropdownMenu.Content align="start">
                        <DropdownMenu.Item
                          className="select-none"
                          onClick={() => onSetBaseline(false)}>
                          {!baselineEnabled ? (
                            <Icon name="checkmark" />
                          ) : (
                            <IconPlaceholder />
                          )}{' '}
                          Compare with previous
                        </DropdownMenu.Item>
                        <DropdownMenu.Item
                          className="select-none"
                          onClick={() => onSetBaseline(true)}>
                          {baselineEnabled ? (
                            <Icon name="checkmark" />
                          ) : (
                            <IconPlaceholder />
                          )}{' '}
                          Compare with baseline
                        </DropdownMenu.Item>
                      </DropdownMenu.Content>
                    </DropdownMenu.Portal>
                  </DropdownMenu.Root>
                )}
              </div>
              <div className="overflow-auto px-16">
                <CompareGrid
                  objectType={objectType}
                  objectIds={filteredObjectIds}
                  objects={filteredObjects}
                  rows={diffed}
                  mode={mode}
                  baselineEnabled={baselineEnabled}
                  onlyChanged={onlyChanged}
                  expandedIds={expandedIds}
                  setExpandedIds={setExpandedIds}
                  addExpandedRefs={addExpandedRefs}
                />
              </div>
            </TailwindContents>
          ),
        },
      ]}
    />
  );
};
