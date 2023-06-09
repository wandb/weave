import {UIConfigOptions} from '@wandb/weave/components/Panel2/panellib/libpanel';
import {Schema} from 'hast-util-sanitize';
import {defaultSchema as gh} from 'hast-util-sanitize/lib/schema';
import {produce} from 'immer';
import * as _ from 'lodash';
import toString from 'mdast-util-to-string';
import katex from 'rehype-katex';
import parseHTML from 'rehype-parse';
import rehypeRaw from 'rehype-raw';
import sanitize from 'rehype-sanitize';
import stringify from 'rehype-stringify';
import emoji from 'remark-emoji';
import math from 'remark-math';
import parse from 'remark-parse';
import remark2rehype from 'remark-rehype';
import {Plugin, unified} from 'unified';
import visit from 'unist-util-visit';

import {blankifyLinks, shiftHeadings} from './html';

const sanitizeRules = _.merge(gh, {
  attributes: {'*': ['className', 'style']},
});

// Hackily convert markdown to text
export function markdownToText(markdown: string) {
  const html = generateHTML(markdown);
  const tempDiv = document.createElement('div');
  tempDiv.innerHTML = html.toString();
  const text = tempDiv.textContent || tempDiv.innerText;
  return text;
}

type SanitizationRules = UIConfigOptions['html'];
export function buildSanitizationSchema(
  rules: SanitizationRules,
  schema: Schema = sanitizeRules
) {
  /**
   * These are all the known transformations that can be triggered through
   * declarative rules passed in from outside weave
   */
  const rulesToSchemaMap: Record<SanitizationRules[number], Schema> = {
    allowScopedStyles: {
      attributes: {
        style: ['scoped'],
      },
      tagNames: ['style'],
    },
  };

  // recursively build up the sanitization object merging in the transformations
  // coupled to each rule
  // NOTE: this assumes rules relax strictness. I'm not sure this model would work for
  // additional strictness on the schema. If we get that scenario we'll need to test
  const newSchema = rules.reduce(
    (schema: Schema, rule: SanitizationRules[number]) => {
      return _.merge(schema, rulesToSchemaMap[rule]);
    },
    schema
  );

  return newSchema;
}

export function generateHTML(
  markdown: string,
  rules: UIConfigOptions['html'] = []
) {
  const sanitizationSchema = buildSanitizationSchema(rules);
  // IMPORTANT: We must sanitize as the final step of the pipeline to prevent XSS
  const vfile = (
    unified()
      .use(parse)
      .use(math)
      .use(emoji)
      .use(centerText)
      .use(remark2rehype, {allowDangerousHtml: true}) as any
  )
    // remark2rehype allows the use of rehype plugins after it in the chain,
    // but it doesn't have its own types, so we're `any`ing here and trusting
    // that the rehype plugins we pass in afterwards will work.
    .use(katex)
    .use(rehypeRaw)
    .use(sanitize, sanitizationSchema)
    .use(stringify)
    .use(sanitize, sanitizationSchema)
    .processSync(markdown);
  if (typeof vfile.value === 'string') {
    vfile.value = blankifyLinks(vfile.value);
    vfile.value = shiftHeadings(vfile.value);
  }
  return vfile;
}

export function sanitizeHTML(html: string) {
  return unified()
    .use(parseHTML)
    .use(stringify as any)
    .use(sanitize, sanitizeRules)
    .processSync(html)
    .toString();
}

// NOTE: The library does not provide the types, this is a partial type
// that types the interface we access here. To use more of the underlying data
// extend this type
interface ASTNode {
  children: ASTNode[];
  type: string;
  value?: string;
  data: {
    hName: string;
    hProperties: {className: string};
  };
  // unknown: unknown
}

// Converts -> Text <- To a centered node in the markdown syntax
// Works at the paragraph level allowing link embedding
const centerText: Plugin = settings => markdownAST => {
  visit(markdownAST, 'paragraph', (node: ASTNode) => {
    const text = toString(node).trim();
    const isCenter =
      text.slice(0, 3) === '-> ' &&
      text.slice(text.length - 3, text.length) === ' <-';

    if (!isCenter) {
      return;
    }
    const originalNode = _.clone(node);
    const last = node.children.length - 1;
    const newChildren = produce(node.children, draft => {
      // Don't use leading ^ for first regex because
      // the AST parsing captures the leading linebreak
      draft[0].value = draft[0]?.value?.trim().replace(/->\s*/, '');
      draft[last].value = draft[last]?.value?.trim().replace(/\s*<-$/, '');
    });
    originalNode.children = newChildren;
    node.type = 'center';
    node.data = {
      hName: 'div',
      hProperties: {className: 'center'},
    };
    node.children = [originalNode];
  });
  return markdownAST;
};

// Heuristic...
export function isMarkdown(str: string): boolean {
  const patterns = [
    /^\s*#{1,6}\s+/, // headings
    /\*\*[^*]+\*\*/, // bold
    /_[^_]+_/, // italic (underscore)
    /\*[^*]+\*/, // italic (asterisk)
    /\[[^\]]+\]\([^)]+\)/, // links
    /^- .+$/, // unordered list
    /^\d+\. .+$/, // ordered list
    /^```/, // code block
    /^> .+$/, // blockquote
    /`[^`]+`/, // inline code
  ];

  return patterns.some(pattern => pattern.test(str));
}
