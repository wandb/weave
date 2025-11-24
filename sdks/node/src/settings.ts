export type SettingsInit =
  | Settings
  | {
      printCallLink?: boolean;
      globalAttributes?: Record<string, any>;
    }
  | undefined;

export class Settings {
  constructor(
    private printCallLink: boolean = true,
    private globalAttributes: Record<string, any> = {}
  ) {}

  get shouldPrintCallLink(): boolean {
    if (process.env.WEAVE_PRINT_CALL_LINK === 'true') {
      return true;
    }
    if (process.env.WEAVE_PRINT_CALL_LINK === 'false') {
      return false;
    }

    return this.printCallLink;
  }

  get attributes(): Record<string, any> {
    return this.globalAttributes;
  }
}
