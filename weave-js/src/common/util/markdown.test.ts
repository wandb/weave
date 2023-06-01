import {generateHTML, isMarkdown} from './markdown';

describe('generateHTML', () => {
  it('does not allow basic script tags', () => {
    const someHTML = '<script>alert(123)</script>';
    console.log(generateHTML(someHTML).value);
    expect(generateHTML(someHTML).value.indexOf('script')).toEqual(-1);
  });

  it('does not allow basic script tags in tag params', () => {
    const someHTML = '<a href=<script>alert(123)</script>> link </a>';
    console.log(generateHTML(someHTML).value);
    expect(generateHTML(someHTML).value.indexOf('script')).toEqual(-1);
  });
});

describe('isMarkdown', () => {
  it('returns true for many kinds of markdown', () => {
    expect(isMarkdown('# heading')).toEqual(true);
    expect(isMarkdown('**bold**')).toEqual(true);
    expect(isMarkdown('_italic_')).toEqual(true);
    expect(isMarkdown('*italic*')).toEqual(true);
    expect(isMarkdown('[link](https://wandb.ai)')).toEqual(true);
    expect(isMarkdown('- list')).toEqual(true);
    expect(isMarkdown('1. list')).toEqual(true);
    expect(isMarkdown('```code```')).toEqual(true);
    expect(isMarkdown('> quote')).toEqual(true);
    expect(isMarkdown('`code`')).toEqual(true);
  });

  it('returns false for many strings that are non-markdown', () => {
    expect(isMarkdown('')).toEqual(false);
    expect(isMarkdown('#')).toEqual(false);
    expect(isMarkdown('**')).toEqual(false);
    expect(isMarkdown('_')).toEqual(false);
    expect(isMarkdown('*')).toEqual(false);
    expect(isMarkdown('[')).toEqual(false);
    expect(isMarkdown('-')).toEqual(false);
    expect(isMarkdown('1.')).toEqual(false);
    expect(isMarkdown('>')).toEqual(false);
    expect(isMarkdown('`')).toEqual(false);
    expect(isMarkdown('not markdown')).toEqual(false);
    expect(isMarkdown('127.0.0.1')).toEqual(false);
    expect(isMarkdown('<script>alert(123)</script>')).toEqual(false);
    expect(isMarkdown('donotreply@wandb.ai')).toEqual(false);
    expect(isMarkdown('http://example.com')).toEqual(false);
    expect(isMarkdown('{"key": "value"}')).toEqual(false);
    expect(isMarkdown('<xml></xml>')).toEqual(false);
    expect(isMarkdown('const x = 1;')).toEqual(false);
    expect(isMarkdown('x = 1')).toEqual(false);
    expect(isMarkdown('2020-01-01T00:00:00.000Z')).toEqual(false);
    expect(isMarkdown('Jan Smith')).toEqual(false);
  });
});
