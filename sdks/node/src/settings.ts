export class Settings {
  constructor(private printCallLink: boolean = true) {}

  get shouldPrintCallLink(): boolean {
    if (process.env.WEAVE_PRINT_CALL_LINK === 'true') {
      return true;
    }
    if (process.env.WEAVE_PRINT_CALL_LINK === 'false') {
      return false;
    }

    return this.printCallLink;
  }
}
