import {render, screen} from '@testing-library/react';
import React from 'react';

import {Tag} from './Tag';

describe('<Tag /> should', () => {
  test('render with the Tailwind wrapper by default', () => {
    render(<Tag label="Test label" />);

    expect(screen.getByTestId('tailwind-wrapper')).toBeInTheDocument();
  });

  test('render a custom wrapper', () => {
    const custom = ({children}: {children: React.ReactNode}) => (
      <div data-testid="paul-blart-mall-cop">{children}</div>
    );
    render(<Tag label="Test label" Wrapper={custom} />);
    expect(screen.getByTestId('paul-blart-mall-cop')).toBeInTheDocument();
  });

  test('Avoid rendering the Tailwind wrapper when directed', () => {
    render(<Tag label="Test label" Wrapper={null} />);
    expect(screen.queryByTestId('tailwind-wrapper')).not.toBeInTheDocument();
  });
});
