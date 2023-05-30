/* eslint-disable jsx-a11y/no-static-element-interactions */
/* eslint-disable jsx-a11y/click-events-have-key-events */
import computeScrollIntoView from 'compute-scroll-into-view';
import * as _ from 'lodash';
import React, {useMemo} from 'react';
import {ThemeProvider} from 'styled-components';

import useControllableState from '../util/controllable';
import * as S from './WBMenu.styles';

export type WBMenuOption = {
  name?: string;
  value: string | number;
  icon?: string | null;
  disabled?: boolean;
  'data-test'?: string;
  render?(props: {hovered: boolean; selected: boolean}): React.ReactNode;
  onSelect?(): void;
};

export function getOptionDisplayName(option: WBMenuOption) {
  return option.name ?? option.value;
}

const scrollIntoView: typeof computeScrollIntoView = (target, options) => {
  const actions = computeScrollIntoView(target, options);
  actions.forEach(({el, top, left}) => {
    if (el !== document.documentElement) {
      el.scrollTop = top;
      el.scrollLeft = left;
    }
  });
  return actions;
};

const DEFAULT_OPTION_RENDERER: OptionRenderer = ({
  option,
  hovered,
  selected,
  fontSize,
  lineHeight,
}) => (
  <S.Item
    data-test={option['data-test']}
    hovered={hovered}
    fontSize={fontSize}
    lineHeight={lineHeight}>
    {getOptionDisplayName(option)}
    <S.ItemIcon
      name={
        option.icon ?? (selected && option.icon !== null ? 'check' : 'blank')
      }
    />
  </S.Item>
);

export type OptionRenderer = (props: {
  option: WBMenuOption;
  hovered: boolean;
  selected: boolean;
  fontSize?: number;
  lineHeight?: number;
}) => React.ReactNode;

export type WBMenuOnSelectHandler = (
  value: string | number,
  extra: {option: WBMenuOption}
) => void;

export type WBMenuTheme = 'dark' | 'light';

export interface WBMenuProps {
  className?: string;
  options: WBMenuOption[];
  optionRenderer?: OptionRenderer;
  // by default expands to fit longest item
  width?: number;
  selected?: string | number;
  selectedRef?: React.Ref<HTMLDivElement>;

  highlightFirst?: boolean;

  highlighted?: string | number | null;
  onChangeHighlighted?: (newHighlight: string | number | null) => void;

  theme?: WBMenuTheme;
  backgroundColor?: string;
  fontSize?: number;
  lineHeight?: number;
  dataTest?: string;
  onSelect?: WBMenuOnSelectHandler;
  onEsc?(): void;
}

export const WBMenu = React.forwardRef<HTMLDivElement, WBMenuProps>(
  (
    {
      className,
      options,
      optionRenderer = DEFAULT_OPTION_RENDERER,
      width,
      selected,
      selectedRef,
      theme = 'dark',
      backgroundColor,
      fontSize,
      lineHeight,
      highlightFirst,
      highlighted: highlightedProp,
      onChangeHighlighted,
      onSelect,
      onEsc,
      dataTest,
    },
    ref
  ) => {
    const getDefaultHoverIndex = React.useCallback(() => {
      let found = -1;
      if (highlightFirst && options.length > 0) {
        found = options.findIndex(opt => !opt.disabled);
      } else {
        found = options.findIndex(opt => selected === opt.value);
      }

      return found >= 0 ? found : 0;
    }, [highlightFirst, options, selected]);
    // dedupe options
    const prevLength = options.length;
    options = _.uniqBy(options, opt => opt.value);
    if (options.length !== prevLength) {
      // eslint-disable-next-line no-console
      console.warn('Passed duplicate options into WBMenu');
    }

    const [highlighted, setHighlighted] = useControllableState(
      options[getDefaultHoverIndex()]?.value || null,
      highlightedProp,
      onChangeHighlighted
    );
    const highlightedIndex = useMemo(() => {
      if (highlighted === null) {
        return null;
      }
      const found = options.findIndex(opt => highlighted === opt.value);

      return found >= 0 ? found : null;
    }, [options, highlighted]);

    const lastHighlightedValue = React.useRef<string | number | null>(
      highlighted
    );
    const setHighlightedWrapped = React.useCallback(
      (newHighlighted: number | string | null) => {
        const last = highlighted;
        setHighlighted(newHighlighted);
        lastHighlightedValue.current = last;
      },
      [highlighted, setHighlighted]
    );

    const contentRef = React.useRef<HTMLDivElement>(null);
    React.useEffect(() => {
      function onKeyDown(e: KeyboardEvent) {
        if (e.keyCode === 38 /* up */) {
          e.preventDefault();
          let moved = false;
          for (
            let i = (highlightedIndex || getDefaultHoverIndex()) - 1;
            i >= -1;
            i--
          ) {
            const modIndex =
              ((i % options.length) + options.length) % options.length;
            if (!options[modIndex].disabled) {
              setHighlightedWrapped(options[modIndex].value);
              const child = contentRef.current?.children[modIndex];
              if (child) {
                scrollIntoView(child, {
                  scrollMode: 'if-needed',
                  block: 'start',
                });
              }
              moved = true;
              break;
            }
          }
          if (!moved && contentRef.current != null) {
            scrollIntoView(contentRef.current, {
              scrollMode: 'if-needed',
              block: 'start',
            });
          }
        }
        if (e.keyCode === 40 /* down */) {
          e.preventDefault();
          let moved = false;
          for (
            let i = (highlightedIndex || getDefaultHoverIndex()) + 1;
            i <= options.length;
            i++
          ) {
            const modIndex =
              ((i % options.length) + options.length) % options.length;
            if (!options[modIndex].disabled) {
              setHighlightedWrapped(options[modIndex].value);
              const child = contentRef.current?.children[modIndex];
              if (child) {
                scrollIntoView(child, {
                  scrollMode: 'if-needed',
                  block: 'end',
                });
              }
              moved = true;
              break;
            }
          }
          if (!moved && contentRef.current != null) {
            scrollIntoView(contentRef.current, {
              scrollMode: 'if-needed',
              block: 'end',
            });
          }
        }
        if (e.keyCode === 13 && !e.shiftKey /* enter */) {
          e.preventDefault();
          if (highlightedIndex != null) {
            onSelect?.(options[highlightedIndex].value, {
              option: options[highlightedIndex],
            });
          }
        }
        if (e.keyCode === 27 /* esc */) {
          e.preventDefault();
          onEsc?.();
        }
      }
      document.addEventListener('keydown', onKeyDown);
      return () => {
        document.removeEventListener('keydown', onKeyDown);
      };
    }, [
      getDefaultHoverIndex,
      highlightedIndex,
      onEsc,
      onSelect,
      options,
      setHighlightedWrapped,
    ]);

    const contentCallbackRef = React.useCallback(
      (node: HTMLDivElement | null) => {
        if (ref) {
          if (typeof ref === 'function') {
            ref(node);
          } else {
            (ref as any).current = node;
          }
        }
        (contentRef as any).current = node;
      },
      [ref]
    );

    const themeObj = useMemo(() => ({main: theme}), [theme]);

    return (
      <ThemeProvider theme={themeObj}>
        <S.Content
          ref={contentCallbackRef}
          className={className}
          width={width}
          backgroundColor={backgroundColor}
          dataTest={dataTest}>
          {options.map((option, i) => {
            const isSelected = selected === option.value;
            const isHovered = highlighted === option.value;
            return (
              <div
                key={option.value}
                data-test="wb-menu-item"
                ref={isSelected ? selectedRef : undefined}
                onMouseEnter={() => {
                  setHighlighted(option.value);
                }}
                style={option.disabled ? {pointerEvents: 'none'} : undefined}
                onMouseDown={e => {
                  e.preventDefault();
                }}
                onClick={e => {
                  e.preventDefault();
                  e.stopPropagation();
                  option.onSelect?.();
                  onSelect?.(option.value, {option});
                }}>
                {option.render
                  ? option.render({
                      hovered: isHovered,
                      selected: isSelected,
                    })
                  : optionRenderer({
                      option,
                      hovered: isHovered,
                      selected: isSelected,
                      fontSize,
                      lineHeight,
                    })}
              </div>
            );
          })}
        </S.Content>
      </ThemeProvider>
    );
  }
);
