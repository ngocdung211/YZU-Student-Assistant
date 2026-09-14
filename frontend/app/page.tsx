'use client';

import { useState } from 'react';
import { Box, Button, Flex, Img, Input, Text, useColorModeValue } from '@chakra-ui/react';
import SidebarContent from '../components/sidebar/SidebarContent';
import Navbar from '../components/navbar/Navbar';

// Layout and style props are adapted from the original HaUI chat page/root layout.
export default function Chat() {
  const [input, setInput] = useState('');
  const sidebarBg = useColorModeValue('white', 'navy.800');
  const textColor = useColorModeValue('navy.700', 'white');
  const inputBg = useColorModeValue('white', 'gray.700');
  const borderColor = useColorModeValue('gray.300', 'whiteAlpha.200');
  const sidebarShadow = useColorModeValue('14px 17px 40px 4px rgba(112, 144, 176, 0.18)', 'unset');

  return (
    <Box>
      <Box as="aside" aria-label="Frequently asked questions" display={{ base: 'none', xl: 'block' }}
        position="fixed" top={0} left={0} h="100dvh" w="300px" bg={sidebarBg} boxShadow={sidebarShadow} zIndex={10}>
        <SidebarContent onQuestionClick={setInput} />
      </Box>
      <Box as="main" ml={{ base: 0, xl: '300px' }} h="100dvh" position="relative" overflow="hidden">
        <Navbar onQuestionClick={setInput} />
        <Img src="/img/logo/yzu-logo.png" alt="" position="absolute" w="400px" maxW="70%" maxH="45dvh" objectFit="contain"
          left="50%" top="45%" opacity="25%" transform="translate(-50%, -50%)" pointerEvents="none" />
        <Flex w="100%" h="100%" direction="column" position="relative">
          <Box h={{ base: '80px', md: '100px' }} flexShrink={0} />
          <Flex flex="1" direction="column" mx="auto" w="100%" maxW="1000px" overflowY="auto"
            px={{ base: '10px', md: '20px' }} pt="20px" pb="160px">
            <Flex w="100%" align="flex-start" mb="20px" mt={5}>
              <Flex borderRadius="full" justify="center" align="center" bg="#ffffff" me="10px"
                h="40px" minH="40px" minW="40px" ml={3} border="1px solid #0d4e96" overflow="hidden">
                <Img src="/img/logo/yzu-logo.png" alt="YZU Student Assistant" w="100%" h="100%" objectFit="contain" />
              </Flex>
              <Flex bg="gray.200" color="gray.800" p="10px" px={{ base: 4, md: 8 }} borderRadius="15px"
                w="600px" maxW="calc(100% - 62px)" boxShadow="0 -2px 8px rgba(0, 0, 0, 0)" direction="column">
                <Text>Hello! I’m the YZU Student Assistant. I can help you find information about university policies, scholarships, and courses.</Text>
              </Flex>
            </Flex>
          </Flex>
          <Flex position="absolute" bottom={0} left={0} w="100%" justify="center" px={{ base: '16px', md: '20px' }} py="10px" direction="column" align="center">
            <Text id="chat-availability" fontSize="xs" color={textColor} mb="8px">Chat is not available yet.</Text>
            <Flex w={{ base: '100%', md: '80%' }} maxW="1000px" align="center" gap="10px" bg={inputBg}
              borderRadius="50px" p="8px" mb="40px" boxShadow="0 4px 20px rgba(0,0,0,0.1)" border="1px solid" borderColor={borderColor}>
              <Input aria-label="Your question" aria-describedby="chat-availability" flex="1" minW={0} border="none" bg="transparent" h="20px"
                px="20px" fontSize="sm" fontWeight="500" color={textColor} placeholder="Type your question..."
                value={input} onChange={(event) => setInput(event.target.value)} />
              {/* Preserve the original input appearance without enabling unimplemented API calls. */}
              <Button variant="primary" h="40px" px="24px" fontSize="sm" borderRadius="50px" flexShrink={0}
                isDisabled _disabled={{ opacity: 1, cursor: 'not-allowed' }} aria-describedby="chat-availability">Send</Button>
            </Flex>
          </Flex>
        </Flex>
      </Box>
    </Box>
  );
}
