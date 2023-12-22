import {Type} from '../../../core/model';
import {IconName} from '../../Icon';
import {getPanelCategory, getPanelIcon} from '../PanelRegistry';
import {getStackIdAndName, PanelSpecNode} from './libpanel';
import {PanelCategory} from './types';

export type StackInfo = {
  readonly id: string;
  readonly displayName: string;
  readonly icon: IconName;
  readonly category: PanelCategory;
};

export function getStackInfo<X, C, T extends Type>(
  panel: PanelSpecNode<X, C, T>
): StackInfo {
  const {id, displayName} = getStackIdAndName(panel);
  const icon = getPanelIcon(id);
  const category = getPanelCategory(id);
  return {
    id,
    displayName,
    icon,
    category,
  };
}
