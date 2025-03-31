import styled from 'styled-components'

export const Wrapper = styled.div<{
  left: number
  height: number
  top: number
}>`
  position: fixed;
  pointer-events: auto;
  z-index: 2147483606;
  left: ${props => props.left}px;
  top: ${props => props.top}px;
  height: ${props => props.height}px;
`

export const Scroller = styled.div<{ contentOverflows?: boolean }>`
  width: 100%;
  height: 100%;
  overflow: ${props => (props.contentOverflows ? `auto` : `visible`)};
  position: relative;

  /* Hide scrollbar */
  scrollbar-width: none; // firefox
  &::-webkit-scrollbar {
    width: 0;
    height: 0;
  }
`
