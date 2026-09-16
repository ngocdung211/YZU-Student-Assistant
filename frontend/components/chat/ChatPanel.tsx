'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import {
  Box, Button, Flex, Img, Input, Spinner, Text, useColorModeValue,
} from '@chakra-ui/react';
import Navbar from '../navbar/Navbar';
import SidebarContent from '../sidebar/SidebarContent';
import { useChatSession } from '../../hooks/useChatSession';
import MarkdownMessage from './MarkdownMessage';
import References from './References';

export default function ChatPanel() {
  const [input, setInput] = useState('');
  const { messages, isLoadingHistory, isSending, isResetting, notice, send, reset } = useChatSession();
  const endRef = useRef<HTMLDivElement>(null);
  const sidebarBg = useColorModeValue('white', 'navy.800');
  const textColor = useColorModeValue('navy.700', 'white');
  const inputBg = useColorModeValue('white', 'gray.700');
  const borderColor = useColorModeValue('gray.300', 'whiteAlpha.200');
  const assistantBg = useColorModeValue('gray.200', 'whiteAlpha.200');
  const sidebarShadow = useColorModeValue(
    '14px 17px 40px 4px rgba(112, 144, 176, 0.18)', 'unset');

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const question = input.trim();
    if (!question) return;
    setInput('');
    const accepted = await send(question);
    if (!accepted) setInput(question);
  }

  return (
    <Box>
      <Box as="aside" aria-label="Frequently asked questions" display={{ base: 'none', xl: 'block' }}
        position="fixed" top={0} left={0} h="100dvh" w="300px" bg={sidebarBg}
        boxShadow={sidebarShadow} zIndex={10}>
        <SidebarContent onQuestionClick={setInput} />
      </Box>
      <Box as="main" ml={{ base: 0, xl: '300px' }} h="100dvh" position="relative" overflow="hidden">
        <Navbar onQuestionClick={setInput} onNewConversation={reset}
          isResetting={isResetting} />
        {messages.length === 0 && !isLoadingHistory && (
          <Img src="/img/logo/yzu-logo.png" alt="" position="absolute" w="400px"
            maxW="70%" maxH="45dvh" objectFit="contain" left="50%" top="45%"
            opacity="25%" transform="translate(-50%, -50%)" pointerEvents="none" />
        )}
        <Flex w="100%" h="100%" direction="column" position="relative">
          <Box h={{ base: '80px', md: '100px' }} flexShrink={0} />
          <Flex flex="1" direction="column" mx="auto" w="100%" maxW="1000px"
            overflowY="auto" px={{ base: '10px', md: '20px' }} pt="20px" pb="150px">
            <Flex w="100%" align="flex-start" mb="20px" mt={5}>
              <AssistantAvatar />
              <Flex bg={assistantBg} color={textColor} p="10px" px={{ base: 4, md: 8 }}
                borderRadius="15px" w="600px" maxW="calc(100% - 62px)" direction="column">
                <Text>Hello! I’m the YZU Student Assistant. I can help you find information about university policies, scholarships, and courses.</Text>
              </Flex>
            </Flex>
            {isLoadingHistory && <Flex justify="center" py={6}><Spinner size="sm" /></Flex>}
            {messages.map((message) => message.role === 'student' ? (
              <Flex key={message.id} justify="flex-end" mb={5}>
                <Box bg="blue.600" color="white" px={{ base: 4, md: 6 }} py={3}
                  borderRadius="15px" maxW="80%">
                  <Text whiteSpace="pre-wrap">{message.content}</Text>
                </Box>
              </Flex>
            ) : (
              <Flex key={message.id} align="flex-start" mb={5}>
                <AssistantAvatar />
                <Box bg={message.state === 'error' ? 'red.50' : assistantBg}
                  color={message.state === 'error' ? 'red.700' : textColor}
                  px={{ base: 4, md: 8 }} py={3} borderRadius="15px"
                  w="700px" maxW="calc(100% - 62px)">
                  {message.state === 'loading' && !message.content ? (
                    <Flex align="center" gap={2}><Spinner size="xs" /><Text>Finding relevant YZU information…</Text></Flex>
                  ) : <MarkdownMessage>{message.content}</MarkdownMessage>}
                  <References references={message.references} />
                </Box>
              </Flex>
            ))}
            <div ref={endRef} />
          </Flex>
          <Flex as="form" onSubmit={submit} position="absolute" bottom={0} left={0}
            w="100%" justify="center" px={{ base: '16px', md: '20px' }} py="10px"
            direction="column" align="center">
            <Text id="chat-status" minH="18px" fontSize="xs"
              color={notice ? 'red.500' : textColor} mb="8px" role={notice ? 'alert' : undefined}>
              {notice || (isSending ? 'Preparing an evidence-based answer…' : 'Answers are based on available YZU sources.')}
            </Text>
            <Flex w={{ base: '100%', md: '80%' }} maxW="1000px" align="center" gap="10px"
              bg={inputBg} borderRadius="50px" p="8px" mb="30px"
              boxShadow="0 4px 20px rgba(0,0,0,0.1)" border="1px solid" borderColor={borderColor}>
              <Input aria-label="Your question" aria-describedby="chat-status" flex="1" minW={0}
                border="none" bg="transparent" h="38px" px="20px" fontSize="sm"
                fontWeight="500" color={textColor} placeholder="Type your question..."
                value={input} onChange={(event) => setInput(event.target.value)}
                maxLength={1000} isDisabled={isSending || isResetting} />
              <Button type="submit" variant="primary" h="40px" px="24px" fontSize="sm"
                borderRadius="50px" flexShrink={0} isLoading={isSending}
                isDisabled={!input.trim() || isResetting}>Send</Button>
            </Flex>
          </Flex>
        </Flex>
      </Box>
    </Box>
  );
}

function AssistantAvatar() {
  return (
    <Flex borderRadius="full" justify="center" align="center" bg="#ffffff" me="10px"
      h="40px" minH="40px" minW="40px" ml={3} border="1px solid #0d4e96" overflow="hidden">
      <Img src="/img/logo/yzu-logo.png" alt="YZU Student Assistant" w="100%" h="100%" objectFit="contain" />
    </Flex>
  );
}
