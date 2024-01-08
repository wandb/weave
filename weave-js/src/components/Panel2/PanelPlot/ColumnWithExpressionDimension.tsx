/**
 * Allow the user to select one or multiple columns as the value.
 * Alternately, allow the user to enter an expression.
 */
import {WeaveInterface} from '@wandb/weave/core';

import {ColumnDimension} from './ColumnDimension';
import {DimensionLike} from './DimensionLike';
import {
  ColumnDimName,
  DropdownWithExpressionMode,
  WeaveExpressionDimension,
} from './plotState';
import {DimState} from './types';
import {SeriesConfig} from './versions';

export class ColumnWithExpressionDimension extends DimensionLike {
  public readonly name: ColumnDimName;
  readonly isMulti: boolean;
  readonly defaultMode: DropdownWithExpressionMode;

  // state managers for expression and dropdown state
  readonly dropdownDim: ColumnDimension;
  readonly expressionDim: WeaveExpressionDimension;

  constructor(
    name: ColumnDimName,
    isMulti: boolean,
    series: SeriesConfig,

    expressionDim: WeaveExpressionDimension,
    dropdownDim: ColumnDimension,
    weave: WeaveInterface
    // defaultMode: DropdownWithExpressionMode = 'dropdown'
  ) {
    super('columnSelWithExpression', name, series, weave);
    this.name = name;
    this.isMulti = isMulti;
    this.dropdownDim = dropdownDim;
    this.expressionDim = expressionDim;
    this.defaultMode = 'dropdown';
    // this.defaultMode = defaultMode;
  }

  mode(): DropdownWithExpressionMode {
    return this.series.uiState[this.name];
  }

  state(): DimState {
    // const mode = this.mode();
    // const childState: DimState =
    //   mode === 'dropdown'
    //     ? this.dropdownDim.state()
    //     : this.expressionDim.state();
    // const compareValue: string = JSON.stringify({
    //   mode,
    //   compareValue: childState.compareValue,
    // });
    // const value: any = {mode, value: childState.value};
    // return {value, compareValue};
    return this.expressionDim.state();
  }

  defaultState(): DimState {
    // const childState = this.dropdownDim.defaultState();
    // const compareValue: string = JSON.stringify({
    //   mode: 'dropdown',
    //   compareValue: childState.compareValue,
    // });
    // const value: any = {mode: 'dropdown', value: childState.value};
    // return {value, compareValue};

    // const childState =
    //   this.defaultMode === 'dropdown'
    //     ? this.dropdownDim.defaultState()
    //     : this.expressionDim.defaultState();
    // const compareValue: string = JSON.stringify({
    //   mode: this.defaultMode,
    //   compareValue: childState.compareValue,
    // });
    // const value: any = {mode: this.defaultMode, value: childState.value};
    // return {value, compareValue};

    return this.expressionDim.defaultState();
  }

  imputeThisSeriesWithDefaultState(): SeriesConfig {
    // const {
    //   value: {mode: defaultMode},
    // } = this.defaultState();
    // const dimWithDefaultMode = produce(this, draft => {
    //   draft.series.uiState[this.name] = defaultMode;
    // });
    // if (defaultMode === 'dropdown') {
    //   return dimWithDefaultMode.dropdownDim.imputeThisSeriesWithDefaultState();
    // } else {
    //   return dimWithDefaultMode.expressionDim.imputeThisSeriesWithDefaultState();
    // }
    return this.expressionDim.imputeThisSeriesWithDefaultState();
  }

  imputeOtherSeriesWithThisState(s: SeriesConfig): SeriesConfig {
    // const mode = this.mode();
    // const newSeries =
    //   mode === 'dropdown'
    //     ? this.dropdownDim.imputeOtherSeriesWithThisState(s)
    //     : this.expressionDim.imputeOtherSeriesWithThisState(s);
    // return produce(newSeries, draft => {
    //   draft.uiState[this.name] = mode;
    // });
    return this.expressionDim.imputeOtherSeriesWithThisState(s);
  }
}
