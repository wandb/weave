import {UserSettings, VegaPanelDef} from '../../util/vega2';
import {Query, Transform} from '../../util/vega3';

export type VegaPanel2Config = Partial<UserSettings> & {
  userQuery?: Query;
  transform?: Transform;
  panelDefId?: string;
  customPanelDef?: VegaPanelDef;
  showRunSelector?: boolean;
  defaultViewedRun?: string;
  defaultViewedStepIndex?: number;
  showStepSelector?: boolean;
};

export function getPanelDefID(
  config: VegaPanel2Config,
  defaultEntityName: string
) {
  if (config.panelDefId && config.panelDefId.startsWith('lib:')) {
    // backwards compatibility
    return (
      defaultEntityName +
      '/' +
      atob(config.panelDefId.split(':')[1]).split(':')[1]
    );
  }
  return config.panelDefId || 'wandb/line/v0';
}
