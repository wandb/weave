import {render, screen, within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import {MemoryRouter} from 'react-router-dom';
import {vi} from 'vitest';

import * as Tabs from './';

describe('Tabs', () => {
  it('displays selected tab', () => {
    render(
      <Tabs.Root value="1">
        <Tabs.List>
          <Tabs.Trigger value="1">Tab 1</Tabs.Trigger>
          <Tabs.Trigger value="2">Tab 2</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="1">Tab 1 contents</Tabs.Content>
        <Tabs.Content value="2">Tab 2 contents</Tabs.Content>
      </Tabs.Root>
    );

    const tablist = screen.getByRole('tablist');
    const allTabs = within(tablist).getAllByRole('tab');
    const selectedTab = within(tablist).getByRole('tab', {selected: true});
    const selectedTabPanel = screen.getByRole('tabpanel', {hidden: false});

    expect(allTabs).toHaveLength(2);
    expect(selectedTab).toHaveTextContent('Tab 1');
    expect(selectedTabPanel).toHaveTextContent('Tab 1 contents');
  });

  it('invokes onValueChange on tab change', async () => {
    const mock = vi.fn();
    render(
      <Tabs.Root value="1" onValueChange={mock}>
        <Tabs.List>
          <Tabs.Trigger value="1">Tab 1</Tabs.Trigger>
          <Tabs.Trigger value="2">Tab 2</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="1">Tab 1 contents</Tabs.Content>
        <Tabs.Content value="2">Tab 2 contents</Tabs.Content>
      </Tabs.Root>
    );
    await userEvent.click(screen.getByRole('tab', {name: 'Tab 2'}));
    expect(mock).toHaveBeenCalledWith('2');
  });

  it('supports disabled tabs', async () => {
    const mock = vi.fn();
    render(
      <Tabs.Root value="1" onValueChange={mock}>
        <Tabs.List>
          <Tabs.Trigger value="1">Tab 1</Tabs.Trigger>
          <Tabs.Trigger value="2" disabled>
            Tab 2
          </Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="1">Tab 1 contents</Tabs.Content>
        <Tabs.Content value="2">Tab 2 contents</Tabs.Content>
      </Tabs.Root>
    );
    await userEvent.click(screen.getByRole('tab', {name: 'Tab 2'}));
    expect(mock).not.toHaveBeenCalled();
  });

  it('supports linked tabs', () => {
    render(
      <MemoryRouter initialEntries={['/tab1']}>
        <Tabs.Root value="/tab1">
          <Tabs.List>
            <Tabs.LinkedTrigger value="/tab1">Tab 1</Tabs.LinkedTrigger>
            <Tabs.LinkedTrigger value="/tab2">Tab 2</Tabs.LinkedTrigger>
          </Tabs.List>
          <Tabs.Content value="/tab1">Tab 1 contents</Tabs.Content>
          <Tabs.Content value="/tab2">Tab 2 contents</Tabs.Content>
        </Tabs.Root>
      </MemoryRouter>
    );
    const tab1 = screen.getByRole('tab', {name: 'Tab 1'});
    const tab2 = screen.getByRole('tab', {name: 'Tab 2'});
    expect(tab1).toHaveAttribute('href', '/tab1');
    expect(tab2).toHaveAttribute('href', '/tab2');
  });
});
