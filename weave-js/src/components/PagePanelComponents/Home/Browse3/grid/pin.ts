import {GridPinnedColumnFields} from '@mui/x-data-grid-pro';
import _ from 'lodash';

const isValidPinValue = (value: any): boolean => {
  return _.isArray(value) && value.every(v => _.isString(v));
};

// Columns that are always pinned left don't need to be present in serialized state.
export const removeAlwaysLeft = (
  pinModel: GridPinnedColumnFields,
  alwaysLeft: string[]
): GridPinnedColumnFields => {
  if (!pinModel.left) {
    return pinModel;
  }
  const {left} = pinModel;
  return {
    ...pinModel,
    left: left.filter(col => !alwaysLeft.includes(col)),
  };
};

// Ensure specified columns are always pinned left.
const ensureAlwaysLeft = (
  pinModel: GridPinnedColumnFields,
  alwaysLeft: string[]
): GridPinnedColumnFields => {
  let left = pinModel.left ?? [];
  left = left.filter(col => !alwaysLeft.includes(col));
  left = alwaysLeft.concat(left);
  return {
    ...pinModel,
    left,
  };
};

export const getValidPinModel = (
  jsonString: string,
  def: GridPinnedColumnFields | null = null,
  alwaysLeft?: string[]
): GridPinnedColumnFields => {
  def = def ?? {};
  try {
    const parsed = JSON.parse(jsonString);
    if (_.isPlainObject(parsed)) {
      const keys = Object.keys(parsed);
      if (
        keys.every(
          key => ['left', 'right'].includes(key) && isValidPinValue(parsed[key])
        )
      ) {
        const pinModel = parsed as GridPinnedColumnFields;
        if (alwaysLeft) {
          return ensureAlwaysLeft(pinModel, alwaysLeft);
        }
        return pinModel;
      }
    }
  } catch (e) {
    // Ignore
  }
  return def;
};
