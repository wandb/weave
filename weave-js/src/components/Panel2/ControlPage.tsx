import {Node, opCount} from '@wandb/weave/core';
import React, {useCallback, useEffect, useMemo} from 'react';

import SliderInput from '../../common/components/elements/SliderInput';
import clamp from '../../common/util/clamp';
import * as LLReact from '../../react';
import * as S from './ControlPage.styles';

const PageControls: React.FC<{
  rowsNode: Node;
  pageSize: number;
  page: number;
  setPage: (page: number) => void;
  shouldUseSlider: boolean;
}> = ({rowsNode, pageSize, page, setPage, shouldUseSlider}) => {
  const countNode = useMemo(() => opCount({arr: rowsNode as any}), [rowsNode]);

  const countValue = LLReact.useNodeValue(countNode);

  // return <div>Row count: {value.result}</div>;
  const startIndex = pageSize * page;
  let endIndex = startIndex + pageSize;
  const totalItems = countValue.result;
  if (endIndex > totalItems) {
    endIndex = totalItems;
  }
  useEffect(() => {
    // reset page if we're out of bounds
    // Note: This code used to try to reset when the input node changed as well,
    // but that causes ugly double loading behavior where the table would load,
    // then we'd reset the page to 0 because it was our first render, which
    // caused a bunch more loading and remounting.
    if (startIndex > totalItems) {
      setPage(0);
    }
  }, [rowsNode, startIndex, totalItems, setPage]);

  const onFirstPage = page === 0;
  const onLastPage = endIndex === totalItems;
  const singleItem = startIndex + 1 === endIndex;

  const prevPage = useCallback(() => {
    if (!onFirstPage) {
      setPage(page - 1);
    }
  }, [page, setPage, onFirstPage]);
  const nextPage = useCallback(() => {
    if (!onLastPage) {
      setPage(page + 1);
    }
  }, [page, setPage, onLastPage]);
  const onSliderChange = useCallback(
    value => setPage(clamp(value - 1, {min: 0, max: totalItems - 1})),
    [setPage, totalItems]
  );

  const controls = shouldUseSlider ? (
    <span
      style={{
        flex: '1 1 auto',
        textAlign: 'center',
      }}>
      <SliderInput
        min={1}
        max={totalItems}
        onChange={onSliderChange}
        step={1}
        value={page + 1}
        hasInput={true}
        debounceTime={100}
      />
    </span>
  ) : (
    <>
      <S.ArrowIcon name="previous" onClick={prevPage} />
      <span
        style={{
          flex: '1 1 auto',
          textAlign: 'center',
        }}>
        {startIndex + 1}
        {!singleItem && `-${endIndex}`} of {totalItems}{' '}
      </span>
      <S.ArrowIcon name="next" onClick={nextPage} />
    </>
  );

  return countValue.loading || countValue.result < 2 ? (
    <></>
  ) : (
    <S.ControlBar>{controls}</S.ControlBar>
  );
};

export default PageControls;
