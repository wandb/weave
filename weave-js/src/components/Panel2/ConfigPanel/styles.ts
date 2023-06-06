import styled from 'styled-components';

export const ConfigOption = styled.div`
  margin-top: 0.5rem;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: top;
`;
ConfigOption.displayName = 'ConfigOption';

export const ConfigOptionLabel = styled.div`
  width: 70px;
  padding-top: 0;
  flex-shrink: 0;
  color: #aaa;
`;
ConfigOptionLabel.displayName = 'ConfigOptionLabel';

export const ConfigOptionField = styled.div`
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
`;
ConfigOptionField.displayName = 'ConfigOptionField';
