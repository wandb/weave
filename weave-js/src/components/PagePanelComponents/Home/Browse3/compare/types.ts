export type ShoppingCartItemDef = {
  key: string;
  value: string;
  label?: string;
};

export type ShoppingCartItemDefs = ShoppingCartItemDef[];

export type ComparableObject = Record<string, any>;
export type ComparableObjects = ComparableObject[];

// For two objects, whether to show side-by-side or unified
export type Mode = 'parallel' | 'unified';
