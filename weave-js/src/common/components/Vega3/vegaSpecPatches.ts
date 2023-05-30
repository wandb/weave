import {produce} from 'immer';
import * as _ from 'lodash';
import {VisualizationSpec} from 'react-vega';
// this file contains functions that patch the vega-lite specs supplied to react-vega.

type VegaSpecFragment = {[key: string]: any};

// add new patch functions to this list
const vegaSpecPatches: Readonly<
  Array<(spec: VisualizationSpec) => VisualizationSpec>
> = [patchScaleToNull];

// replace all instances of {scale: {}} with {scale: null} in the spec.
function patchScaleToNull(spec: VisualizationSpec): VisualizationSpec {
  // this patch is needed because our function deepMapArraysAndValues converts
  // object leaf nodes that are null to {}. we need scale to be null for reading
  // data that is directly encoded as values (i.e., has no scale). so we manually
  // set scale to null here, calling this after deepMapArraysAndValues has already
  // been called in injectFields in CustomPanelRenderer
  const recursivelyMutateSpec = (draft: VegaSpecFragment): void => {
    for (const key of Object.keys(draft)) {
      const value = draft[key];
      if (key === 'scale' && _.isEmpty(value)) {
        draft[key] = null;
      } else if (value === null) {
        return;
      } else if (typeof value === 'object') {
        recursivelyMutateSpec(value);
      }
    }
  };

  return produce(spec, recursivelyMutateSpec);
}

// this is the only function that this file should export
export function patchWBVegaSpec(spec: VisualizationSpec): VisualizationSpec {
  return vegaSpecPatches.reduce((memo, patch) => patch(memo), spec);
}
