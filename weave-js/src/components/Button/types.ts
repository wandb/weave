export const ButtonSizes = {
  Small: 'small',
  Medium: 'medium',
  Large: 'large',
} as const;
export type ButtonSize = (typeof ButtonSizes)[keyof typeof ButtonSizes];

export const ButtonVariants = {
  Primary: 'primary',
  Secondary: 'secondary',
  Ghost: 'ghost',
  Quiet: 'quiet',
  Destructive: 'destructive',
} as const;
export type ButtonVariant =
  (typeof ButtonVariants)[keyof typeof ButtonVariants];
