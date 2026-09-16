'use client';

import { Box, Link, Text, VStack } from '@chakra-ui/react';
import { FiExternalLink } from 'react-icons/fi';
import { ChatReference } from '../../lib/chat';

export default function References({ references }: { references: ChatReference[] }) {
  if (references.length === 0) return null;
  return (
    <Box mt={4} pt={3} borderTop="1px solid" borderColor="blackAlpha.200">
      <Text fontSize="xs" fontWeight="700" mb={2}>Sources</Text>
      <VStack align="stretch" spacing={1}>
        {references.map((reference) => {
          const pages = reference.page_numbers.length > 0
            ? ` — page${reference.page_numbers.length > 1 ? 's' : ''} ${reference.page_numbers.join(', ')}`
            : '';
          return (
            <Link key={reference.source_id} href={reference.source_url} isExternal
              rel="noopener noreferrer" fontSize="xs" color="blue.600">
              {reference.title}{pages} <Box as={FiExternalLink} display="inline" ml="2px" />
            </Link>
          );
        })}
      </VStack>
    </Box>
  );
}
