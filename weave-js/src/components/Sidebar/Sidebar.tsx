import React from 'react';
import {Icon} from 'semantic-ui-react';

import * as S from './Sidebar.styles';

export function getConfigWithDefaults(configSpec: any, config: any) {
  const spec = configSpec || {};
  const result = {} as any;
  for (const key of Object.keys(spec)) {
    result[key] = config[key] ?? spec[key].default;
  }
  return result;
}

interface SidebarProps {
  className?: string;
  collapsed: boolean;
  close: () => void;
}

export const Sidebar: React.FC<SidebarProps> = props => {
  const {close, collapsed, children} = props;
  return (
    <>
      <S.Wrapper
        data-test="weave-sidebar"
        className={props.className}
        collapsed={collapsed}>
        <S.Title>
          <S.BarButton data-test="panel-config" onClick={() => close()}>
            <Icon name="x" />
          </S.BarButton>
        </S.Title>
        <S.Main>{children}</S.Main>
      </S.Wrapper>
    </>
  );
};

export default Sidebar;
