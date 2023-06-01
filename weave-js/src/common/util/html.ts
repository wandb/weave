export function blankifyLinks(html: string): string {
  return html.replace(/<a href="[^"]+"/g, match => `${match} target="_blank"`);
}

// HAX: We don't want users adding h1s for SEO purposes, so we shift the headings down 1 level
export function shiftHeadings(html: string): string {
  return html
    .replace(/<h5>/g, '<h6>')
    .replace(/<\/h5>/g, '</h6>')
    .replace(/<h4>/g, '<h5>')
    .replace(/<\/h4>/g, '</h5>')
    .replace(/<h3>/g, '<h4>')
    .replace(/<\/h3>/g, '</h4>')
    .replace(/<h2>/g, '<h3>')
    .replace(/<\/h2>/g, '</h3>')
    .replace(/<h1>/g, '<h2>')
    .replace(/<\/h1>/g, '</h2>');
}

export function escapeHTML(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
