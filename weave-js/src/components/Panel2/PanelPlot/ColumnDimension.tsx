/**
 * Allow the user to select one or multiple columns as the value.
 */
import {WeaveInterface} from '@wandb/weave/core';
import produce from 'immer';

import {DimensionLike} from './DimensionLike';
import {ColumnDimName, DropdownOption} from './plotState';
import {DimState} from './types';
import {SeriesConfig} from './versions';

export class ColumnDimension extends DimensionLike {
  public readonly options: DropdownOption[];
  public readonly name: ColumnDimName;
  // public readonly placeholder?: string;
  protected readonly defaultOptions: DropdownOption[];

  constructor(
    name: ColumnDimName,
    series: SeriesConfig,
    weave: WeaveInterface,
    options: DropdownOption[],
    defaultOptions: DropdownOption[]
  ) {
    super('optionSelect', name, series, weave);
    this.options = options;
    this.name = name;
    this.defaultOptions = defaultOptions;
  }

  imputeThisSeriesWithDefaultState(): SeriesConfig {
    return produce(this.series, draft => {
      // // @ts-ignore
      // draft.constants[this.name] = this.defaultOption.value;
    });
  }

  imputeOtherSeriesWithThisState(s: SeriesConfig): SeriesConfig {
    return produce(s, draft => {
      // // @ts-ignore
      // draft.constants[this.name] = this.state().value;
    });
  }

  defaultState(): DimState {
    return {
      value: null,
      compareValue: '',
      // value: this.defaultOption.value,
      // compareValue: this.defaultOption.text,
    };
  }

  state(): DimState {
    return {
      value: null,
      compareValue: '',
    };
    // const value = this.series.constants[this.name];
    // const option = this.options.find(o => o.value === value);
    // return {value, compareValue: option ? option.text : ''};
  }
}
