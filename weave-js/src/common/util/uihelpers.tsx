import {DropdownItemProps} from 'semantic-ui-react';

import {RequireSome} from '../types/base';

export type Option = RequireSome<DropdownItemProps, 'value' | 'text'> & {
  content?: DropdownItemProps['content'];
  key?: DropdownItemProps['key'];
};
