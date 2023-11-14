import {MOON_800, MOON_850} from '@wandb/weave/common/css/color.styles';
import styled from 'styled-components';

export const Title = styled.div`
  color: ${MOON_850};
  font-size: 24px;
  font-weight: 600;
  line-height: 40px;
`;
Title.displayName = 'S.Title';

export const Description = styled.div`
  color: ${MOON_800};
  font-size: 16px;
  font-weight: 400;
  line-height: 140%;
  margin-bottom: 16px;
`;
Description.displayName = 'S.Description';

export const Buttons = styled.div`
  margin-top: 24px;
  display: flex;
  gap: 8px;
`;
Buttons.displayName = 'S.Buttons';
