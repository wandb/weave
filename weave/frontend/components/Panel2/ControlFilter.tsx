import * as S from './ControlFilter.styles';
import React, {useCallback, useMemo, useState} from 'react';
import {Button} from 'semantic-ui-react';
import makeComp from '@wandb/common/util/profiler';
import * as HL from '@wandb/cg/browser/hl';
import * as Code from '@wandb/cg/browser/code';
import * as ExpressionEditor from './ExpressionEditor';
import * as Types from '@wandb/cg/browser/model/types';
import * as CGTypes from '@wandb/cg/browser/types';
import {voidNode} from '@wandb/cg/browser/graph';

interface ControlFilterProps {
  frame: Code.Frame;
  filterFunction: Types.NodeOrVoidNode;
  setFilterFunction(newNode: Types.NodeOrVoidNode): void;
}

export const ControlFilter: React.FC<ControlFilterProps> = makeComp(
  ({
    frame,
    filterFunction: propsFilterFunction,
    setFilterFunction: propsSetFilterFunction,
  }) => {
    const [filterFunction, setFilterFunction] =
      useState<CGTypes.EditingNode>(propsFilterFunction);
    const isValid =
      HL.nodeIsExecutable(filterFunction) &&
      (filterFunction.nodeType === 'void' ||
        Types.isAssignableTo(filterFunction.type, Types.maybe('boolean')));
    const updateFilterFunction = useCallback(() => {
      if (HL.nodeIsExecutable(filterFunction) && isValid) {
        propsSetFilterFunction(filterFunction);
      } else {
        setFilterFunction(propsFilterFunction);
      }
    }, [propsFilterFunction, propsSetFilterFunction, filterFunction, isValid]);

    const isClean = useMemo(() => {
      return (
        (propsFilterFunction.nodeType === 'void' &&
          filterFunction.nodeType === 'void') ||
        propsFilterFunction === filterFunction
      );
    }, [propsFilterFunction, filterFunction]);

    const removable = useMemo(() => {
      return propsFilterFunction.nodeType === 'output';
    }, [propsFilterFunction.nodeType]);

    return (
      <S.FilterControls>
        <div style={{flex: '1 1 auto', paddingBottom: '5px'}}>
          <ExpressionEditor.ExpressionEditor
            frame={frame}
            node={filterFunction}
            updateNode={setFilterFunction}
            focusOnMount
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
  },
  {id: 'ControlFilter', memo: true}
);
