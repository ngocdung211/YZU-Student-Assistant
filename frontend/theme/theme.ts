import { extendTheme } from '@chakra-ui/react';
import { globalStyles } from './styles';
import { buttonStyles } from './button';

// Reuse the HaUI theme and its font for Chakra headings as well as body text.
export default extendTheme(globalStyles, buttonStyles, {
  fonts: { body: "'Plus Jakarta Sans', sans-serif", heading: "'Plus Jakarta Sans', sans-serif" },
  config: { initialColorMode: 'light', useSystemColorMode: false },
});
