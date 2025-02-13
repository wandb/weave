// Test for MyComponent
import {render, screen} from '@testing-library/react';
import React from 'react';

import {Tailwind, TailwindContents} from './Tailwind';

describe('Tailwind wrapper', () => {
  test('empty wrapper includes defaults', () => {
    render(<Tailwind />);

    // Assertions
    const wrapper = screen.getByTestId('tailwind-wrapper');
    expect(wrapper).toBeInTheDocument();
    expect(wrapper).toHaveClass('tw-style');
  });

  test('wrapper includes defined props', () => {
    render(<Tailwind style={{minHeight: '500px'}} className="myClass" />);

    // Assertions
    const wrapper = screen.getByTestId('tailwind-wrapper');
    expect(wrapper).toBeInTheDocument();
    expect(wrapper).toHaveClass('tw-style');
    expect(wrapper).toHaveStyle('min-height: 500px');
    expect(wrapper).toHaveClass('myClass');
  });

  test('wrapper includes extended props', () => {
    render(<Tailwind data-test="mytest" />);

    // Assertions
    const wrapper = screen.getByTestId('tailwind-wrapper');
    console.log(wrapper);
    expect(wrapper).toBeInTheDocument();
    expect(wrapper).toHaveClass('tw-style');
    expect(wrapper).toHaveAttribute('data-test', 'mytest');
  });

  test('wrapper includes override props', () => {
    render(<Tailwind data-test="mytest" data-testid="mytestid" />);

    // Assertions
    const wrapper = screen.getByTestId('mytestid');
    console.log(wrapper);
    expect(wrapper).toBeInTheDocument();
    expect(wrapper).toHaveClass('tw-style');
    expect(wrapper).toHaveAttribute('data-test', 'mytest');
    expect(wrapper).toHaveAttribute('data-testid', 'mytestid');
    expect(wrapper).not.toHaveAttribute('data-testid', 'tailwind-wrapper');
  });

  test('contents wrapper includes defaults', () => {
    render(<TailwindContents />);

    // Assertions
    const wrapper = screen.getByTestId('tailwind-wrapper');
    expect(wrapper).toBeInTheDocument();
    expect(wrapper).toHaveClass('tw-style');
    expect(wrapper).toHaveStyle('display: contents');
  });

  test('contents wrapper includes defined props', () => {
    render(
      <TailwindContents style={{minHeight: '500px'}} className="myClass" />
    );

    // Assertions
    const wrapper = screen.getByTestId('tailwind-wrapper');
    expect(wrapper).toBeInTheDocument();
    expect(wrapper).toHaveClass('tw-style');
    expect(wrapper).toHaveStyle('display: contents');
    expect(wrapper).toHaveStyle('min-height: 500px');
    expect(wrapper).toHaveClass('myClass');
  });

  test('contents wrapper includes extended props', () => {
    render(<TailwindContents data-test="mytest" />);

    // Assertions
    const wrapper = screen.getByTestId('tailwind-wrapper');
    expect(wrapper).toBeInTheDocument();
    expect(wrapper).toHaveClass('tw-style');
    expect(wrapper).toHaveStyle('display: contents');
    expect(wrapper).toHaveAttribute('data-test', 'mytest');
  });

  test('contents wrapper includes override props', () => {
    render(<TailwindContents data-test="mytest" data-testid="mytestid" />);

    // Assertions
    const wrapper = screen.getByTestId('mytestid');
    expect(wrapper).toBeInTheDocument();
    expect(wrapper).toHaveClass('tw-style');
    expect(wrapper).toHaveStyle('display: contents');
    expect(wrapper).toHaveAttribute('data-test', 'mytest');
    expect(wrapper).toHaveAttribute('data-testid', 'mytestid');
  });
});
