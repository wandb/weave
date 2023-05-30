export function printPDFInNewWindow(
  url: string,
  name: string,
  width: number,
  height: number
): void {
  // eslint-disable-next-line wandb/no-unprefixed-urls
  const w = window.open(url, name, `width=${width},height=${height}`);
  if (w == null) {
    return;
  }
  w.document.title = name;
  w.print();
}
