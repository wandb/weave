import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useMemo, useRef} from 'react';

import {Button} from '../../../../../../../Button';
import {useCompareEvaluationsState} from '../../compareEvaluationsContext';
import {
  EvaluationComparisonState,
  getOrderedCallIds,
  getOrderedEvalsWithNewBaseline,
  swapEvaluationCalls,
} from '../../ecpState';
import {HorizontalBox} from '../../Layout';
import {ItemDef} from '../DraggableSection/DraggableItem';
import {DraggableSection} from '../DraggableSection/DraggableSection';
import {EvaluationSelector} from './EvaluationSelector';

export const ComparisonDefinitionSection: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const {setEvaluationCallOrder, removeEvaluationCall} =
    useCompareEvaluationsState();

  const callIds = useMemo(() => {
    return getOrderedCallIds(props.state);
  }, [props.state]);

  const items: ItemDef[] = useMemo(() => {
    return callIds.map(callId => ({
      key: 'evaluations',
      value: callId,
      label: props.state.summary.evaluationCalls[callId]?.name ?? callId,
    }));
  }, [callIds, props.state.summary.evaluationCalls]);

  const onSetBaseline = (value: string | null) => {
    if (!value) {
      return;
    }
    const newSortOrder = getOrderedEvalsWithNewBaseline(callIds, value);
    setEvaluationCallOrder(newSortOrder);
  };
  const onRemoveItem = (value: string) => removeEvaluationCall(value);
  const onSortEnd = ({
    oldIndex,
    newIndex,
  }: {
    oldIndex: number;
    newIndex: number;
  }) => {
    const newSortOrder = swapEvaluationCalls(callIds, oldIndex, newIndex);
    setEvaluationCallOrder(newSortOrder);
  };

  return (
    <Tailwind>
      <div className="flex w-full items-center gap-4 overflow-x-auto pl-16">
        <HorizontalBox>
          <DraggableSection
            useDragHandle
            axis="x"
            state={props.state}
            items={items}
            onSetBaseline={onSetBaseline}
            onRemoveItem={onRemoveItem}
            onSortEnd={onSortEnd}
            useWindowAsScrollContainer
          />
        </HorizontalBox>
        <HorizontalBox>
          <AddEvaluationButton state={props.state} />
        </HorizontalBox>
      </div>
    </Tailwind>
  );
};

const AddEvaluationButton: React.FC<{
  state: EvaluationComparisonState;
}> = props => {
  const {addEvaluationCall} = useCompareEvaluationsState();

  // Popover management
  const refBar = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const onClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : refBar.current);
  };
  const onClose = () => {
    setAnchorEl(null);
  };

  const onSelect = (callId: string) => {
    addEvaluationCall(callId);
    setAnchorEl(null);
  };

  const currentEvalIds = getOrderedCallIds(props.state);

  return (
    <>
      <div ref={refBar} onClick={onClick}>
        <Button variant="ghost" size="large" icon="add-new">
          Add evaluation
        </Button>
      </div>
      <EvaluationSelector
        entity={props.state.summary.entity}
        project={props.state.summary.project}
        anchorEl={anchorEl}
        onSelect={onSelect}
        onClose={onClose}
        excludeEvalIds={currentEvalIds}
      />
    </>
  );
};
