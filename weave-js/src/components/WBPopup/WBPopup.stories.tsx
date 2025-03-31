import { Meta, Story } from '@storybook/react'
import React from 'react'
import styled from 'styled-components'

import { WBMenu, WBMenuProps } from '../WBMenu'
import * as WBMenuStories from '../WBMenu/WBMenu.stories'
import { WBPopup, WBPopupProps } from './WBPopup'

const Dot = styled.div<{ x: number; y: number }>`
  position: fixed;
  top: ${props => props.y - 4}px;
  left: ${props => props.x - 4}px;
  background: red;
  border-radius: 4px;
  width: 8px;
  height: 8px;
`

const meta: Meta = {
  component: WBPopup,
  title: 'Legacy/WBPopup',
  parameters: {
    docs: {
      inlineStories: false
    }
  }
}
export default meta

const Template: Story<WBPopupProps> = args => (
  <>
    <Dot x={args.x} y={args.y} />
    <WBPopup {...args}></WBPopup>
  </>
)

export const Basic = Template.bind({})
Basic.args = {
  x: 300,
  y: 40,
  direction: 'bottom center',
  children: <>Hello world!</>
}

export const WithMenu = Template.bind({})
WithMenu.args = {
  ...Basic.args,
  children: <WBMenu {...(WBMenuStories.Basic.args as WBMenuProps)} />
}
