'use client';

import { Fragment } from 'react';
import { Box, Button, Divider, Flex, Heading, VStack, useColorModeValue } from '@chakra-ui/react';

const questions = [
  'Where can I find YZU university policies?',
  'What scholarships are available to YZU students?',
  'What are the scholarship application requirements?',
  'Where can I find a list of courses?',
  'Can you explain the information for a course?',
  'Where can I read the original university documents?',
];

// Adapted from HaUI-library/src/components/sidebar/components/Content.tsx.
export default function SidebarContent({ onQuestionClick }: { onQuestionClick: (question: string) => void }) {
  const textColor = useColorModeValue('navy.700', 'white');
  const bgColor = useColorModeValue('white', 'navy.700');
  return (
    <Flex direction="column" h="100%" bg={bgColor} fontSize={15} px="20px" py="20px" justifyContent="space-between">
      <Flex alignItems="center" justifyContent="center" minH="35px">
        <Box as="img" src="/img/logo/yzu-logo.png" alt="Yuan Ze University" height="80px" width="80px" objectFit="contain" />
      </Flex>
      <Box flex="1" mt="8px" overflowY="auto" py="10px">
        <Heading fontSize="lg" mb={4} color={textColor}>Frequently asked questions:</Heading>
        <VStack spacing={3} align="stretch">
          {questions.map((question, index) => (
            <Fragment key={question}>
              <Button variant="ghost" size="sm" p="3px" h="auto" whiteSpace="normal" textAlign="left"
                justifyContent="flex-start" borderRadius="8px" color={textColor} fontSize="sm" lineHeight="1.4"
                _hover={{ bg: bgColor, transform: 'translateY(-1px)', boxShadow: 'sm' }}
                onClick={() => onQuestionClick(question)} transition="all 0.2s ease">
                {question}
              </Button>
              {index < questions.length - 1 && <Divider my={1} />}
            </Fragment>
          ))}
        </VStack>
      </Box>
      <Flex mt="8px" boxShadow="4px 17px 40px 4px rgba(112, 144, 176, 0.08)" borderRadius="30px" p="14px" />
    </Flex>
  );
}
