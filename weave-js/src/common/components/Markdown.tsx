// main prismjs needs to be imported first before prism-markdown
/* eslint-disable simple-import-sort/imports */
import * as Prism from 'prismjs';

import 'prismjs/components/prism-markdown';

import React, {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import {Item} from 'semantic-ui-react';
import vfile from 'vfile';

import {generateHTML} from '../util/markdown';

const formatContent = async (content: string, condensed?: boolean) => {
  if (!content || content.length === 0) {
    return '';
  }
  if (condensed) {
    const parts = content.split(/#+/);
    content = parts[0].length === 0 ? '### ' + parts[1] : parts[0];
    return await generateHTML(content);
  } else {
    return await generateHTML(content);
  }
};

interface MarkdownEditorProps {
  content: string;
  condensed?: boolean;
  onContentHeightChange?(h: number): void;
}

const Markdown: React.FC<MarkdownEditorProps> = ({
  content,
  condensed,
  onContentHeightChange,
}) => {
  const ref = useRef<HTMLDivElement>(null);
  const [html, setHTML] = useState<string | vfile.VFile>(
    '<div class="ui active loader"/>'
  );

  useEffect(() => {
    let cancelled = false;
    formatContent(content, condensed).then(formatted => {
      if (cancelled) {
        return;
      }
      setHTML(formatted);
    });

    return () => {
      cancelled = true;
    };
  }, [content, condensed]);

  useLayoutEffect(() => {
    if (ref.current) {
      const code = ref.current.querySelectorAll('code');
      // tslint:disable-next-line:prefer-for-of
      for (let i = 0; i < code.length; i++) {
        Prism.highlightElement(code[i]);
      }
    }
  }, [html]);

  const lastHeight = useRef<number | null>(null);

  const updateHeight = useCallback(() => {
    const contentHeight = ref.current?.offsetHeight;
    if (contentHeight != null && contentHeight !== lastHeight.current) {
      lastHeight.current = contentHeight;
      onContentHeightChange?.(contentHeight);
    }
  }, [onContentHeightChange]);

  useEffect(() => {
    if (ref.current == null || onContentHeightChange == null) {
      return;
    }
    window.addEventListener('resize', updateHeight);

    // Images load asynchronously and affect the content height
    const imgs = ref.current.querySelectorAll('img');
    // We have to use classic for loop here because IE doesn't support NodeList.forEach()
    // See https://developer.mozilla.org/en-US/docs/Web/API/NodeList#Example
    // tslint:disable-next-line:prefer-for-of
    for (let i = 0; i < imgs.length; i++) {
      const img = imgs[i];
      img.addEventListener('load', updateHeight);
    }

    updateHeight();
    return () => {
      window.removeEventListener('resize', updateHeight);
    };
  });

  useLayoutEffect(() => {
    updateHeight();
  }, [html, updateHeight]);

  return (
    <div ref={ref} className="markdown-content">
      <Item.Description
        className={condensed ? '' : 'markdown'}
        dangerouslySetInnerHTML={{
          __html: html,
        }}
      />
    </div>
  );
};
export default Markdown;
