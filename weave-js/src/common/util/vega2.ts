export interface FieldSettings {
  [key: string]: string;
}

export interface UserSettings {
  fieldSettings: FieldSettings;
  stringSettings: FieldSettings;
}

export interface VegaPanelDef {
  name?: string;
  displayName: string;
  description: string;
  spec: string;
  access?: string;
}
