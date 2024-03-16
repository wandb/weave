import {WeaveInterface} from '@wandb/weave/core';
import {immerable, produce} from 'immer';
import _ from 'lodash';

import {DimName, DimState, DimType} from './types';
import {SeriesConfig} from './versions';

/* A DimensionLike object is as a container for the state of a single config panel UI component
 or group of related components for a single series. DimensionLike objects can be compared
 to other DimensionLike objects, and can perform immutable state updates on SeriesConfig
 objects.
 */
export abstract class DimensionLike {
  readonly type: DimType;
  readonly name: DimName;
  readonly series: SeriesConfig;

  // lets us use produce() to create new instances of these classes via mutation
  public [immerable] = true;

  protected readonly weave: WeaveInterface;

  protected constructor(
    type: DimType,
    name: DimName,
    series: SeriesConfig,
    weave: WeaveInterface
  ) {
    this.type = type;
    this.name = name;
    this.series = series;
    this.weave = weave;
  }

  withSeries(series: SeriesConfig): DimensionLike {
    return produce(this, draft => {
      draft.series = series;
    });
  }

  // abstract method to impute a series with the default value for this dimension, returning a new series
  abstract imputeThisSeriesWithDefaultState(): SeriesConfig;

  // given another series, return
  abstract imputeOtherSeriesWithThisState(s: SeriesConfig): SeriesConfig;

  isVoid(): boolean {
    return _.isEqual(
      this.state().compareValue,
      this.defaultState().compareValue
    );
  }

  // return true if two dimensions are the same type, have the same state, have the same name, and
  // have equal children. optionally return true if at least one of the dimensions is in the void state
  equals(other: DimensionLike, tolerateVoid: boolean = false): boolean {
    return (
      this.type === other.type &&
      this.name === other.name &&
      (_.isEqual(this.state().compareValue, other.state().compareValue) ||
        (tolerateVoid && (this.isVoid() || other.isVoid())))
    );
  }

  // default state of the dimension, e.g., mark setting = undefined for mark, null expression for weave
  abstract defaultState(): DimState;

  // current state of the dimension e.g., mark setting for mark, or table Select function for expression dim
  abstract state(): DimState;
}
