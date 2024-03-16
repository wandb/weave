import {LegacyWBIcon} from '@wandb/weave/common/components/elements/LegacyWBIcon';
import HighlightedIcon from '@wandb/weave/common/components/HighlightedIcon';
import {PopupDropdown} from '@wandb/weave/common/components/PopupDropdown';
import {ConstNode, constString} from '@wandb/weave/core';
import {produce} from 'immer';
import _ from 'lodash';
import React, {ReactNode, useCallback, useMemo} from 'react';
import {MenuItemProps} from 'semantic-ui-react';
import styled from 'styled-components';

import {
  useWeaveContext,
  useWeaveRedesignedPlotConfigEnabled,
} from '../../../context';
import {Button} from '../../Button';
import {IconLockedConstrained, IconUnlockedUnconstrained} from '../../Icon';
import {PopupMenu, Section} from '../../Sidebar/PopupMenu';
import {Tooltip} from '../../Tooltip';
import {
  IconAddNew,
  IconCheckmark,
  IconDelete,
  IconFullScreenModeExpand,
  IconMinimizeMode,
  IconWeave,
} from '../Icons';
import * as TableState from '../PanelTable/tableState';
import {ConfigDimLabel} from './ConfigDimLabel';
import {ConfigSelect} from './ConfigSelect';
import * as PlotState from './plotState';
import * as S from './styles';
import {DimComponentInputType, DimOption, DimOptionOrSection} from './types';
import {PLOT_DIMS_UI, SeriesConfig} from './versions';
import {WeaveExpressionDimConfig} from './WeaveExpressionDimConfig';

const IconBlank = styled.svg`
  width: 18px;
  height: 18px;
`;
IconBlank.displayName = 'S.IconBlank';

export const ConfigDimComponent: React.FC<DimComponentInputType> = props => {
  const {
    updateConfig,
    config,
    dimension,
    isShared,
    indentation,
    input,
    extraOptions,
    multiline,
  } = props;
  const weave = useWeaveContext();
  const redesignedPlotConfigEnabled = useWeaveRedesignedPlotConfigEnabled();
  const makeUnsharedDimDropdownOptions = useCallback(
    (series: SeriesConfig, dimName: (typeof PLOT_DIMS_UI)[number]) => {
      const removeSeriesDropdownOption =
        config.series.length > 1
          ? {
              text: 'Remove series',
              icon: 'wbic-ic-delete',
              onClick: () => {
                updateConfig(PlotState.removeSeries(config, series));
              },
            }
          : null;

      const addSeriesDropdownOption = {
        text: 'Add series from this series',
        icon: 'wbic-ic-plus',
        onClick: () => {
          const newConfig = PlotState.addSeriesFromSeries(
            config,
            series,
            dimName,
            weave
          );
          updateConfig(newConfig);
        },
      };

      const collapseDimDropdownOption =
        config.series.length > 1
          ? {
              text: 'Collapse dimension',
              icon: 'wbic-ic-collapse',
              onClick: () => {
                updateConfig(
                  PlotState.makeDimensionShared(config, series, dimName, weave)
                );
              },
            }
          : null;

      return redesignedPlotConfigEnabled
        ? []
        : [
            removeSeriesDropdownOption,
            addSeriesDropdownOption,
            collapseDimDropdownOption,
            redesignedPlotConfigEnabled,
          ];
    },
    [config, updateConfig, weave, redesignedPlotConfigEnabled]
  );

  const makeSharedDimDropdownOptions = useCallback(
    (dimName: (typeof PLOT_DIMS_UI)[number]) => {
      const expandDim =
        config.series.length > 1
          ? {
              text: 'Expand dimension',
              icon: 'wbic-ic-expand',
              onClick: () => {
                const newConfig = produce(config, draft => {
                  draft.configOptionsExpanded[dimName] = true;
                });
                updateConfig(newConfig);
              },
            }
          : null;

      return redesignedPlotConfigEnabled ? [] : [expandDim];
    },
    [config, updateConfig, redesignedPlotConfigEnabled]
  );

  const uiStateOptions = useMemo(() => {
    if (!PlotState.isDropdownWithExpression(dimension)) {
      return [null];
    }

    // return true if an expression can be directly switched to a constant
    const isDirectlySwitchable = (
      dim: PlotState.DropdownWithExpressionDimension
    ): boolean => {
      const options = dim.dropdownDim.options;
      const expressionValue = dim.expressionDim.state().value;
      const expressionIsConst = expressionValue.nodeType === 'const';
      return options.some(
        o =>
          expressionIsConst &&
          _.isEqual(o.value, (expressionValue as ConstNode).val) &&
          o.representableAsExpression
      );
    };

    const clickHandler = (
      dim: PlotState.DropdownWithExpressionDimension,
      kernel: (
        series: SeriesConfig,
        dimension: PlotState.DropdownWithExpressionDimension
      ) => void
    ): void => {
      const newConfig = produce(config, draft => {
        const seriesToIterateOver = isShared
          ? draft.series
          : _.compact([
              draft.series.find(series => _.isEqual(series, dim.series)),
            ]);
        seriesToIterateOver.forEach(s => kernel(s, dim));
      });

      updateConfig(newConfig);
    };

    return [
      [
        {
          text: 'Input method',
          icon: null,
          disabled: true,
        },
        {
          text: 'Select via dropdown',
          icon: !redesignedPlotConfigEnabled ? (
            'wbic-ic-list'
          ) : dimension.mode() === `dropdown` ? (
            <IconCheckmark />
          ) : (
            <IconBlank />
          ),
          active: dimension.mode() === 'dropdown',
          onClick: () => {
            clickHandler(dimension, (s, dim) => {
              if (s.uiState[dim.name] === 'expression') {
                s.uiState[dim.name] = 'dropdown';
                const expressionValue = dim.expressionDim.state().value;

                // If the current expression has a corresponding dropdown option, use that dropdown value
                if (isDirectlySwitchable(dim)) {
                  s.constants[dim.name] = (expressionValue as ConstNode)
                    .val as any;
                }
              }
            });
          },
        },
        {
          text: 'Enter a Weave Expression',
          icon: !redesignedPlotConfigEnabled ? (
            'wbic-ic-xaxis'
          ) : dimension.mode() === `expression` ? (
            <IconCheckmark />
          ) : (
            <IconBlank />
          ),

          active: dimension.mode() === 'expression',
          onClick: () => {
            clickHandler(dimension, (s, dim) => {
              if (s.uiState[dim.name] === 'dropdown') {
                s.uiState[dim.name] = 'expression';

                // If the current dropdown is representable as an expression, use that expression
                if (isDirectlySwitchable(dim)) {
                  const colId = s.dims[dim.name];
                  s.table = TableState.updateColumnSelect(
                    s.table,
                    colId,
                    constString(s.constants[dim.name])
                  );
                }
              }
            });
          },
        },
      ],
    ];
  }, [config, updateConfig, isShared, dimension, redesignedPlotConfigEnabled]);

  const topLevelDimOptions = useCallback(
    (dimName: (typeof PLOT_DIMS_UI)[number]) => {
      return isShared
        ? makeSharedDimDropdownOptions(dimName)
        : makeUnsharedDimDropdownOptions(dimension.series, dimName);
    },
    [
      makeSharedDimDropdownOptions,
      makeUnsharedDimDropdownOptions,
      dimension.series,
      isShared,
    ]
  );

  const dimOptions = useMemo(
    () =>
      _.compact([
        ...(PlotState.isTopLevelDimension(dimension.name)
          ? topLevelDimOptions(dimension.name)
          : []),
        ...uiStateOptions,
        ...(extraOptions || []),
      ]),
    [dimension, uiStateOptions, topLevelDimOptions, extraOptions]
  );

  const postFixComponent = useMemo(() => {
    if (!redesignedPlotConfigEnabled) {
      return (
        <PopupDropdown
          position="left center"
          trigger={
            <div>
              <HighlightedIcon>
                <LegacyWBIcon name="overflow" />
              </HighlightedIcon>
            </div>
          }
          options={dimOptions.filter(o => !Array.isArray(o))}
          sections={dimOptions.filter(o => Array.isArray(o)) as DimOption[][]}
        />
      );
    }

    const nonArrayDimOptions = dimOptions.filter(
      o => !Array.isArray(o)
    ) as DimOption[];
    const arrayDimOptions = dimOptions.filter(o =>
      Array.isArray(o)
    ) as DimOption[][];

    const menuItems: MenuItemProps[] =
      nonArrayDimOptions.map(dimOptionToMenuItem);
    const menuSections: Section[] = arrayDimOptions.map(opts => ({
      label: opts[0].text,
      items: opts.slice(1).map(dimOptionToMenuItem),
    }));

    const zeroMenuOptions =
      uiStateOptions.length === 1 &&
      uiStateOptions[0] === null &&
      extraOptions == null;

    const dimName = dimension.name as (typeof PLOT_DIMS_UI)[number];

    return (
      <>
        {!zeroMenuOptions && (
          <PopupMenu
            position="bottom left"
            trigger={
              <Button variant="ghost" size="small" icon="overflow-horizontal" />
            }
            items={menuItems}
            sections={menuSections}
          />
        )}
        {config.series.length > 1 &&
          indentation === 0 &&
          (isShared ? (
            <Tooltip
              position="top right"
              trigger={
                <S.ConstrainedIconContainer
                  onClick={() => {
                    // "expanding" the dimension means unconstraining it
                    const newConfig = produce(config, draft => {
                      draft.configOptionsExpanded[dimName] = true;
                    });
                    updateConfig(newConfig);
                  }}>
                  <IconLockedConstrained width={18} height={18} />
                </S.ConstrainedIconContainer>
              }>
              Remove constraint across series
            </Tooltip>
          ) : (
            <Tooltip
              position="top right"
              trigger={
                <S.UnconstrainedIconContainer
                  // "sharing" the dimension means constraining it
                  onClick={() => {
                    updateConfig(
                      PlotState.makeDimensionShared(
                        config,
                        dimension.series,
                        dimName,
                        weave
                      )
                    );
                  }}>
                  <IconUnlockedUnconstrained width={18} height={18} />
                </S.UnconstrainedIconContainer>
              }>
              Constrain dimension across series
            </Tooltip>
          ))}
      </>
    );

    function dimOptionToMenuItem({
      text,
      icon,
      onClick,
    }: DimOption): MenuItemProps {
      return {
        key: text,
        content: text,
        icon: convertIcon(icon),
        onClick,
      };
    }

    function convertIcon(iconStr: ReactNode): ReactNode {
      if (typeof iconStr !== `string`) {
        return iconStr;
      }
      switch (iconStr) {
        case `wbic-ic-delete`:
          return <IconDelete />;
        case `wbic-ic-plus`:
          return <IconAddNew />;
        case `wbic-ic-collapse`:
          // TODO: replace with proper icon
          return <IconMinimizeMode />;
        case `wbic-ic-expand`:
          // TODO: replace with proper icon
          return <IconFullScreenModeExpand />;
        case null:
          return null;
        default:
          return <IconWeave />;
      }
    }
  }, [
    dimOptions,
    redesignedPlotConfigEnabled,
    config,
    dimension.name,
    dimension.series,
    extraOptions,
    indentation,
    isShared,
    uiStateOptions,
    updateConfig,
    weave,
  ]);

  if (PlotState.isDropdownWithExpression(dimension)) {
    return (
      <ConfigDimComponent
        {...props}
        dimension={
          dimension.mode() === 'expression'
            ? dimension.expressionDim
            : dimension.dropdownDim
        }
        extraOptions={uiStateOptions as DimOptionOrSection[]}
      />
    );
  } else if (PlotState.isGroup(dimension)) {
    const primary = dimension.primaryDimension();
    return (
      <>
        {dimension.activeDimensions().map(dim => {
          const isPrimary = dim.equals(primary);
          return (
            <ConfigDimComponent
              {...props}
              key={dim.name}
              indentation={isPrimary ? indentation : indentation + 1}
              dimension={dim}
            />
          );
        })}
      </>
    );
  } else if (PlotState.isDropdown(dimension)) {
    const dimName = dimension.name;
    return (
      <ConfigDimLabel
        {...props}
        postfixComponent={postFixComponent}
        multiline={redesignedPlotConfigEnabled && multiline}
        redesignedPlotConfigEnabled={redesignedPlotConfigEnabled}>
        <ConfigSelect
          testId={`dropdown-${dimName}`}
          placeholder={dimension.defaultState().compareValue}
          value={dimension.state().value}
          options={dimension.options}
          onChange={({value}) => {
            const newSeries = produce(config.series, draft => {
              draft.forEach(s => {
                if (isShared || _.isEqual(s, dimension.series)) {
                  // @ts-ignore
                  s.constants[dimName] = value;
                }
              });
            });
            updateConfig({
              series: newSeries,
            });
          }}
        />
      </ConfigDimLabel>
    );
  } else if (PlotState.isWeaveExpression(dimension)) {
    return (
      <ConfigDimLabel
        {...props}
        postfixComponent={postFixComponent}
        multiline={redesignedPlotConfigEnabled && multiline}
        redesignedPlotConfigEnabled={redesignedPlotConfigEnabled}>
        <WeaveExpressionDimConfig
          dimName={dimension.name}
          input={input}
          config={config}
          updateConfig={updateConfig}
          series={isShared ? config.series : [dimension.series]}
        />
      </ConfigDimLabel>
    );
  }
  return null;
};
