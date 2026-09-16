'use client';

import { Box } from '@chakra-ui/react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function MarkdownMessage({ children }: { children: string }) {
  return (
    <Box sx={{
      '& > :first-of-type': { mt: 0 },
      '& > :last-child': { mb: 0 },
      'p, ul, ol, table, pre': { mb: 3 },
      'ul, ol': { pl: 6 },
      table: { display: 'block', overflowX: 'auto', borderCollapse: 'collapse' },
      'th, td': { border: '1px solid', borderColor: 'gray.300', px: 3, py: 2 },
      th: { bg: 'blackAlpha.100', textAlign: 'left' },
      code: { bg: 'blackAlpha.100', borderRadius: '4px', px: 1 },
      pre: { overflowX: 'auto', bg: 'blackAlpha.100', borderRadius: '8px', p: 3 },
      'pre code': { bg: 'transparent', p: 0 },
      a: { color: 'blue.600', textDecoration: 'underline' },
    }}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </Box>
  );
}
