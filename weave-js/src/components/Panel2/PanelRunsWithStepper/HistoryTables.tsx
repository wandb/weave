import {LIST_RUNS_TYPE} from '@wandb/weave/common/types/run';

import * as Panel2 from '../panel';
import {TableSpec} from '../PanelTable/PanelTable';
import {
  buildPanelRunsWithStepper,
  PanelRunsWithStepperConfigType,
} from './base';

export const Spec: Panel2.PanelSpec<PanelRunsWithStepperConfigType> = {
  id: 'run-history-tables-stepper',
  displayName: 'Run History Tables Stepper',
  Component: buildPanelRunsWithStepper(TableSpec),
  inputType: LIST_RUNS_TYPE,
  outputType: () => ({
    type: 'list' as const,
    objectType: {
      type: 'list' as const,
      objectType: {type: 'typedDict' as const, propertyTypes: {}},
    },
  }),
};
