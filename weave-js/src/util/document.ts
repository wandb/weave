export function setDocumentTitle(
  title: string,
  appendWeave: boolean = true
): void {
  if (appendWeave) {
    title += ' – Weave';
  }
  document.title = title;
}
