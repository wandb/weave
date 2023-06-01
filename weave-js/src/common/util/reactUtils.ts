import * as _ from 'lodash';

// Common props used for prop pass through
export interface NameProps {
  className?: string;
  id?: string;
}

export function pickNameProps<T>(props: T) {
  return _.pick(props, ['className', 'id']) as NameProps;
}
