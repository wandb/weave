import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';

import {TruncateByCharsWithTooltip} from './TruncateByCharsWithTooltip';
import {truncateTextByChars} from './utils';

describe('TruncateTextByCharsWithTooltip', () => {
  it('includes tooltip if text is truncated', async () => {
    render(
      <TruncateByCharsWithTooltip text="hello world" maxChars={5}>
        {({truncatedText}) => <p>{truncatedText}</p>}
      </TruncateByCharsWithTooltip>
    );
    await userEvent.hover(screen.getByRole('button', {name: 'hello…'}));
    expect(await screen.findByRole('tooltip')).toHaveTextContent('hello world');
  });

  it('does NOT include tooltip if text is NOT truncated', () => {
    render(
      <TruncateByCharsWithTooltip text="hello" maxChars={10}>
        {({truncatedText}) => <p>{truncatedText}</p>}
      </TruncateByCharsWithTooltip>
    );
    expect(screen.getByText('hello')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument(); // tooltip trigger is a button
  });

  it('omits tailwind wrapper if null wrapper is specified', () => {
    render(
      <TruncateByCharsWithTooltip
        text="hello world"
        maxChars={5}
        Wrapper={null}>
        {({truncatedText}) => <p>{truncatedText}</p>}
      </TruncateByCharsWithTooltip>
    );
    expect(screen.queryByTestId('tailwind-wrapper')).not.toBeInTheDocument();
  });
});

describe('truncateTextByChars', () => {
  it('does not truncate texts shorter than maxChars', () => {
    expect(truncateTextByChars('hello', 10, 'end')).toEqual('hello');
  });

  it('supports start truncation', () => {
    expect(truncateTextByChars('hello world', 5, 'start')).toEqual('…world');
  });

  it('supports middle truncation with odd maxChars', () => {
    expect(truncateTextByChars('hello world', 5, 'middle')).toEqual('hel…ld');
  });

  it('supports middle truncation with even maxChars', () => {
    expect(truncateTextByChars('hello world', 6, 'middle')).toEqual('hel…rld');
  });

  it('supports end truncation', () => {
    expect(truncateTextByChars('hello world', 5, 'end')).toEqual('hello…');
  });
});
