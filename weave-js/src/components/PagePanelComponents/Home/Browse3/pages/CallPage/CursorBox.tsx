import Box from '@mui/material/Box';
import styled from 'styled-components';

// MUI Box doesn't support cursor
// https://github.com/mui/material-ui/issues/19983
export const CursorBox = styled(Box)<{$isClickable: boolean}>`
  cursor: ${p => (p.$isClickable ? 'pointer' : 'default')};
`;
CursorBox.displayName = 'S.CursorBox';
