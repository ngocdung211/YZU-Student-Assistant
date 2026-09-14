import { mode } from '@chakra-ui/theme-tools';

// Retain the original HaUI primary-button variant.
export const buttonStyles = {
  components: {
    Button: {
      variants: {
        primary: (props: any) => ({
          bg: mode(
            'linear-gradient(15.46deg, #0d4e96 26.3%, #0d4e96 86.4%)',
            'linear-gradient(15.46deg, #0d4e96 26.3%, #0d4e96 86.4%)',
          )(props),
          color: 'white',
          boxShadow: 'none',
          _focus: {
            bg: mode(
              'linear-gradient(15.46deg, #41A2EB 26.3%, #41A2EB 86.4%)',
              'linear-gradient(15.46deg, #41A2EB 26.3%, #41A2EB 86.4%)',
            )(props),
          },
          _active: {
            bg: mode(
              'linear-gradient(15.46deg, #41A2EB 26.3%, #41A2EB 86.4%)',
              'linear-gradient(15.46deg, #41A2EB 26.3%, #41A2EB 86.4%)',
            )(props),
          },
          _hover: {
            boxShadow: '0px 21px 27px -10px rgba(96, 60, 255, 0.48) !important',
            bg: mode(
              'linear-gradient(15.46deg,rgb(24, 95, 175) 26.3%, rgb(24, 95, 175) 86.4%)',
              'linear-gradient(15.46deg, rgb(24, 95, 175) 26.3%, rgb(24, 95, 175) 86.4%)',
            )(props),
          },
        }),
      },
    },
  },
};
