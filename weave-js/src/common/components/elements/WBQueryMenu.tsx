import React from 'react';
import {Loader} from 'semantic-ui-react';

import {WBMenu, WBMenuOption, WBMenuProps} from '../WBMenu';
import * as S from './WBQueryMenu.styles';

const DEFAULT_SORT_SCORE_FN = () => {
  return 0;
};

export interface WBMenuOptionFetcherResult {
  nextPageCursor?: string;
  options: WBMenuOption[];
}

export type WBMenuOptionFetcher = (pageOptions: {
  cursor?: string;
  count: number;
}) => Promise<WBMenuOptionFetcherResult>;

export type SortScoreFn = (option: WBMenuOption) => number;

export type WBQueryMenuProps = Omit<WBMenuProps, 'options'> & {
  scrollerElement?: HTMLElement | null;
  scrollThreshold?: number;
  pageSize?: number;
  options?: WBMenuOption[] | WBMenuOptionFetcher;
  dataTest?: string;
  sortScoreFn?: SortScoreFn;
  infiniteScroll?: boolean;
  onResolvedOptions?: (options: WBMenuOption[]) => void;
};

const WBQueryMenu = React.forwardRef<HTMLDivElement, WBQueryMenuProps>(
  (
    {
      options,
      scrollerElement,
      scrollThreshold = 52,
      pageSize = 20,
      sortScoreFn = DEFAULT_SORT_SCORE_FN,
      infiniteScroll,
      onResolvedOptions,
      ...rest
    },
    ref
  ) => {
    const [loading, setLoading] = React.useState(typeof options === 'function');
    const [computedOptions, setComputedOptions] = React.useState<
      WBMenuOption[]
    >([]);
    const [nextPageCursor, setNextPageCursor] = React.useState<
      string | undefined
    >(undefined);
    const [defaultScrollerElement, setDefaultScrollerElement] =
      React.useState<HTMLDivElement | null>(null);
    const lastQueryRan =
      React.useRef<Promise<WBMenuOptionFetcherResult> | null>(null);
    React.useEffect(() => {
      // prevent queries from updating state after unmount
      return () => {
        lastQueryRan.current = null;
      };
    }, []);
    React.useEffect(() => {
      if (typeof options === 'function') {
        setComputedOptions([]);
        setLoading(true);
        const thisQuery = options({count: pageSize});
        lastQueryRan.current = thisQuery;
        thisQuery.then(result => {
          if (thisQuery === lastQueryRan.current) {
            setNextPageCursor(result.nextPageCursor);
            setComputedOptions(result.options);
            onResolvedOptions?.(result.options);
            setLoading(false);
          }
        });
      } else if (Array.isArray(options)) {
        if (infiniteScroll) {
          setComputedOptions(options.slice(0, pageSize));
        } else {
          setComputedOptions(options);
        }
        onResolvedOptions?.(options);
      }
    }, [options, pageSize, onResolvedOptions, infiniteScroll]);

    let modifiedOptions = computedOptions.slice();
    if (loading) {
      modifiedOptions.push({
        value: -1,
        disabled: true,
        render: () => (
          <S.LoaderItem>
            <Loader active size="tiny"></Loader>
          </S.LoaderItem>
        ),
      });
    } else if (computedOptions.length === 0) {
      modifiedOptions = [
        {
          value: -1,
          disabled: true,
          render: () => <S.DisabledItem>No matches</S.DisabledItem>,
        },
      ];
    }

    if (!infiniteScroll) {
      // can't do frontend sorting if using infinite scroll
      computedOptions.sort((a, b) => {
        const aScore = sortScoreFn(a);
        const bScore = sortScoreFn(b);
        if (aScore !== bScore) {
          return bScore - aScore;
        }
        return 0;
      });
    }

    const loadMore = React.useCallback(() => {
      if (typeof options === 'function') {
        setLoading(true);
        const thisQuery = options({
          cursor: nextPageCursor,
          count: pageSize,
        });
        lastQueryRan.current = thisQuery;
        thisQuery.then(result => {
          if (thisQuery === lastQueryRan.current) {
            setComputedOptions(opts => opts.concat(result.options));
            setNextPageCursor(result.nextPageCursor);
            setLoading(false);
          }
        });
      } else {
        if (Array.isArray(options)) {
          setComputedOptions(opts => options.slice(0, opts.length + pageSize));
        }
      }
    }, [pageSize, options, nextPageCursor]);

    if (scrollerElement == null) {
      scrollerElement = defaultScrollerElement;
    }

    React.useEffect(() => {
      if (scrollerElement != null) {
        const onScrollerScroll = () => {
          const allLoaded =
            (typeof options === 'function' &&
              !loading &&
              nextPageCursor == null) ||
            (Array.isArray(options) &&
              computedOptions.length === options.length);
          if (
            scrollerElement != null &&
            infiniteScroll &&
            !allLoaded &&
            scrollerElement.scrollTop >
              scrollerElement.scrollHeight -
                scrollerElement.clientHeight -
                scrollThreshold
          ) {
            loadMore();
          }
        };
        scrollerElement.addEventListener('scroll', onScrollerScroll);
        return () => {
          scrollerElement?.removeEventListener('scroll', onScrollerScroll);
        };
      }
      return;
    }, [
      scrollerElement,
      computedOptions,
      infiniteScroll,
      loadMore,
      loading,
      scrollThreshold,
      options,
      nextPageCursor,
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
        setDefaultScrollerElement(node);
      },
      [ref]
    );

    return (
      <WBMenu
        {...rest}
        ref={contentCallbackRef}
        options={modifiedOptions}></WBMenu>
    );
  }
);

export default WBQueryMenu;
