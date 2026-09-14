'use client';

import type { ReactNode } from 'react';
import { ChakraProvider } from '@chakra-ui/react';
import theme from '../theme/theme';

// Adapted from HaUI-library/app/AppWrappers.tsx.
export default function AppWrappers({ children }: { children: ReactNode }) {
  return <ChakraProvider theme={theme}>{children}</ChakraProvider>;
}
