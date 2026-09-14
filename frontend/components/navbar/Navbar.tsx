'use client';

import {
  Box, Flex, IconButton, Drawer, DrawerBody, DrawerOverlay, DrawerContent, DrawerCloseButton,
  Menu, MenuButton, MenuList, Text, useColorMode, useColorModeValue, useDisclosure,
} from '@chakra-ui/react';
import { IoMenuOutline } from 'react-icons/io5';
import { IoMdMoon, IoMdSunny } from 'react-icons/io';
import { MdInfoOutline } from 'react-icons/md';
import SidebarContent from '../sidebar/SidebarContent';

// Reuse the floating toolbar and responsive drawer from the HaUI navbar/sidebar.
export default function Navbar({ onQuestionClick }: { onQuestionClick: (question: string) => void }) {
  const { isOpen, onOpen, onClose } = useDisclosure();
  const { colorMode, toggleColorMode } = useColorMode();
  const menuBg = useColorModeValue('white', 'navy.800');
  const iconColor = useColorModeValue('gray.500', 'white');
  const shadow = useColorModeValue('14px 17px 40px 4px rgba(112, 144, 176, 0.18)', '0px 41px 75px #081132');
  return (
    <>
      <Box as="header" zIndex={20} position="fixed" right={{ base: '12px', md: '30px' }} top={{ base: '12px', md: '18px' }}>
        <Flex alignItems="center" bg={menuBg} p="20px" borderRadius="30px" boxShadow={shadow} gap="10px">
          <IconButton aria-label="Open frequently asked questions" icon={<IoMenuOutline size={20} />} variant="unstyled" minW="20px" h="20px" color={iconColor} onClick={onOpen} />
          <Menu>
            <MenuButton as={IconButton} aria-label="About the assistant" icon={<MdInfoOutline size={18} />} variant="unstyled" minW="18px" h="20px" color={iconColor} />
            <MenuList boxShadow={shadow} p="20px" borderRadius="20px" bg={menuBg} border="none" mt="22px" maxW="280px">
              <Text fontWeight="bold">YZU Student Assistant</Text>
              <Text fontSize="sm" mt="8px">Chat is not available yet.</Text>
            </MenuList>
          </Menu>
          <IconButton aria-label={colorMode === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
            icon={colorMode === 'light' ? <IoMdMoon size={18} /> : <IoMdSunny size={18} />}
            variant="unstyled" minW="18px" h="20px" color={iconColor} onClick={toggleColorMode} />
        </Flex>
      </Box>
      <Drawer isOpen={isOpen} onClose={onClose} placement="left">
        <DrawerOverlay />
        <DrawerContent w="285px" maxW="285px" m="16px" borderRadius="16px" bg={menuBg}>
          <DrawerCloseButton zIndex={3} />
          <DrawerBody px={0} pt="32px" pb={0}>
            <SidebarContent onQuestionClick={(question) => { onQuestionClick(question); onClose(); }} />
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </>
  );
}
