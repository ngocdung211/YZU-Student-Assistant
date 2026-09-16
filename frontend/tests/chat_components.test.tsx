import { ChakraProvider } from '@chakra-ui/react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import MarkdownMessage from '../components/chat/MarkdownMessage';
import References from '../components/chat/References';

describe('chat rendering', () => {
  it('renders GitHub-flavored Markdown tables without enabling raw HTML', () => {
    const html = renderToStaticMarkup(
      <ChakraProvider>
        <MarkdownMessage>
          {'| Requirement | Value |\n|---|---|\n| GPA | 3.5 |\n\n<script>alert(1)</script>'}
        </MarkdownMessage>
      </ChakraProvider>,
    );
    expect(html).toContain('<table>');
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(html).not.toContain('<script>');
  });

  it('renders structured references as protected external links', () => {
    const html = renderToStaticMarkup(
      <ChakraProvider>
        <References references={[{
          source_id: 'source-1',
          chunk_id: 'chunk-1',
          document_id: 'document-1',
          title: 'Scholarship rules',
          source_url: 'https://drive.google.com/file/d/test/view',
          page_numbers: [2, 3],
          source_type: 'document',
        }]} />
      </ChakraProvider>,
    );
    expect(html).toContain('href="https://drive.google.com/file/d/test/view"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer"');
    expect(html).toContain('pages 2, 3');
  });
});
