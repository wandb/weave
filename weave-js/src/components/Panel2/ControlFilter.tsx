import {
  EditingNode,
  isAssignableTo,
  maybe,
  NodeOrVoidNode,
  voidNode,
} from '@wandb/weave/core';
import React, {useCallback, useMemo, useState} from 'react';
import {Button} from 'semantic-ui-react';

import {useWeaveContext} from '../../context';
import {focusEditor, WeaveExpression} from '../../panel/WeaveExpression';
import * as S from './ControlFilter.styles';

interface ControlFilterProps {
  filterFunction: NodeOrVoidNode;
  setFilterFunction(newNode: NodeOrVoidNode): void;
}

export const ControlFilter: React.FC<ControlFilterProps> = React.memo(
  ({
    filterFunction: propsFilterFunction,
    setFilterFunction: propsSetFilterFunction,
  }) => {
    const weave = useWeaveContext();
    const [filterFunction, setFilterFunction] =
      useState<EditingNode>(propsFilterFunction);
    const isValid =
      weave.nodeIsExecutable(filterFunction) &&
      (filterFunction.nodeType === 'void' ||
        isAssignableTo(filterFunction.type, maybe('boolean')));
    const updateFilterFunction = useCallback(() => {
      if (weave.nodeIsExecutable(filterFunction) && isValid) {
        propsSetFilterFunction(filterFunction);
      } else {
        setFilterFunction(propsFilterFunction);
      }
    }, [
      propsFilterFunction,
      propsSetFilterFunction,
      filterFunction,
      isValid,
      weave,
    ]);

    const isClean = useMemo(() => {
      return (
        (propsFilterFunction.nodeType === 'void' &&
          filterFunction.nodeType === 'void') ||
        propsFilterFunction === filterFunction
      );
    }, [propsFilterFunction, filterFunction]);

    const removable = useMemo(() => {
      return propsFilterFunction.nodeType !== 'void';
    }, [propsFilterFunction.nodeType]);

    return (
      <S.FilterControls>
        <div style={{flex: '1 1 auto', paddingBottom: '5px'}}>
          <WeaveExpression
            expr={filterFunction}
            setExpression={setFilterFunction}
            onMount={focusEditor}
            liveUpdate
          />
        </div>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
          }}>
          <div>
            <Button
              data-test="filter-apply"
              disabled={!isValid}
              onClick={updateFilterFunction}
              size="mini"
              primary={!isClean || undefined}>
              {isClean ? 'Close' : 'Apply'}
            </Button>
            {!isClean && (
              <Button
                onClick={() => {
                  propsSetFilterFunction(propsFilterFunction);
                }}
                size="mini">
                Discard Changes
              </Button>
            )}
          </div>
          <div>
            {removable && (
              <Button
                data-test="filter-remove"
                onClick={() => {
                  propsSetFilterFunction(voidNode());
                }}
                size="mini"
                color="red">
                Remove Filter
              </Button>
            )}
          </div>
        </div>
      </S.FilterControls>
    );
  }
);
