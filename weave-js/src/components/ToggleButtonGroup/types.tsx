export const ToggleButtonGroupSizes = {
  Small: 'small',
  Medium: 'medium',
  Large: 'large',
} as const;
export type ToggleButtonGroupSize = (typeof ToggleButtonGroupSizes)[keyof typeof ToggleButtonGroupSizes];
