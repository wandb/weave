export const CalloutSizes = {
  XSmall: 'x-small',
  Small: 'small',
  Medium: 'medium',
  Large: 'large',
} as const;
export type CalloutSize = (typeof CalloutSizes)[keyof typeof CalloutSizes];
