import {
  OnParentScrollOption,
  OptionRenderer,
  WBMenuOnSelectHandler,
  WBMenuOption,
} from '@wandb/ui';
import React from 'react';

import {
  SortScoreFn,
  WBMenuOptionFetcher,
  WBMenuOptionFetcherResult,
} from './WBQueryMenu';
import * as S from './WBSuggester.styles';

const DEFAULT_OPTION_RENDERER: OptionRenderer = ({option, hovered}) => (
  <S.Option hovered={hovered}>{option.name ?? option.value}</S.Option>
);

export type WBSuggesterOptionFetcher = (
  query: string,
  pageOptions: {cursor?: string; count: number}
) => Promise<WBMenuOptionFetcherResult>;

export type WBSuggesterUser = (props: {
  inputRef: (node: HTMLElement | null) => void;
}) => React.ReactNode;

export interface WBSuggesterProps {
  className?: string;
  /**
   * Gives Autocompleter the same width as the input element.
   */
  matchWidth?: boolean;
  maxHeight?: number;
  /**
   * Can be a list of options or a function that fetches options for a given query.
   * If options isn't defined, autocompleting is disabled.
   */
  options?: WBMenuOption[] | WBSuggesterOptionFetcher;
  /**
   * Load more options when you scroll to the bottom.
   * Requires that the fetcher returns pageOptions.
   */
  infiniteScroll?: boolean;
  children: WBSuggesterUser;
  onSelect: WBMenuOnSelectHandler;
  optionRenderer?: OptionRenderer;
  query: string;
  /**
   * How to behave when the scrolling container is scrolled.
   * Can accept a custom handler.
   */
  onParentScroll?: OnParentScrollOption;

  /**
   *  Whether to display the suggestion menu.
   */
  open: boolean;

  /**
   * Content to display next to the menu, when the menu is open.
   */
  contextContent?: React.ReactChild | null;

  /**
   * The number of pixels above the bottom you can scroll before loading the next page.
   */
  scrollThreshold?: number;
  /**
   * The number of items to be fetched at a time.
   * Doesn't apply when options are hardcoded.
   */
  pageSize?: number;
  /**
   * Which option is currently selected. Strictly cosmetic.
   */
  selected?: string | number;

  /**
   * Value to apply to the data-test property of the underlying DOM element.
   */
  dataTest?: string;

  /**
   * A function that computes a score for an option, used in sorting.
   * Higher scoring options appear first.
   */
  sortScoreFn?: SortScoreFn;
  onResolvedOptions?: (options: WBMenuOption[]) => void;
}

const WBSuggester: React.FC<WBSuggesterProps> = ({
  className,
  matchWidth,
  maxHeight = 248,
  options,
  dataTest,
  selected,
  onSelect,
  children,
  query,
  onParentScroll,
  open,
  scrollThreshold,
  pageSize,
  optionRenderer = DEFAULT_OPTION_RENDERER,
  infiniteScroll,
  sortScoreFn,
  onResolvedOptions,
  contextContent,
}) => {
  const defaultSortScoreFn: SortScoreFn = option => {
    const s = option.name ?? option.value.toString();
    return s.startsWith(query) ? 1 : 0;
  };

  const [inputEl, setInputEl] = React.useState<HTMLElement | null>(null);

  let filteredOptions: WBMenuOption[] | WBMenuOptionFetcher | undefined;
  if (Array.isArray(options)) {
    filteredOptions = options.filter(o =>
      (o.name ?? o.value)
        ?.toString()
        .toLowerCase()
        .includes(query.toLowerCase())
    );
  } else if (typeof options === 'function') {
    filteredOptions = pageOptions => {
      return options(query, pageOptions);
    };
  }

  return (
    <>
      {children({
        inputRef: setInputEl,
      })}
      {filteredOptions != null && open && (
        <S.SuggestionMenuPopup
          className={className}
          direction="bottom right"
          anchorElement={inputEl}
          triangleSize={0}
          onParentScroll={onParentScroll}>
          <S.SuggestionPopupFlexWrapper>
            <S.SuggestionMenu
              $maxHeight={maxHeight}
              // hack to reset hovered item (for keyboard selection) only when the query changes
              width={
                matchWidth ? inputEl?.getBoundingClientRect().width : undefined
              }
              dataTest={dataTest}
              options={filteredOptions}
              highlightFirst
              selected={selected}
              pageSize={pageSize}
              sortScoreFn={sortScoreFn || defaultSortScoreFn}
              scrollThreshold={scrollThreshold}
              infiniteScroll={infiniteScroll}
              onSelect={(v, extra) => {
                onSelect(v, extra);
              }}
              optionRenderer={optionRenderer}
              onResolvedOptions={onResolvedOptions}></S.SuggestionMenu>
            {contextContent && (
              <S.SuggestionContext
                data-test="suggestion-context"
                // we trap mouseDown events inside the context so that we can click things inside of it
                // (otherwise the whole tooltip will close before you can mouseUp, making a full click impossible)
                onMouseDown={e => e.preventDefault()}>
                {contextContent}
              </S.SuggestionContext>
            )}
          </S.SuggestionPopupFlexWrapper>
        </S.SuggestionMenuPopup>
      )}
    </>
  );
};

export default WBSuggester;
