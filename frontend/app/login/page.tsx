'use client';

import {
  Alert, AlertIcon, Box, Button, Container, FormControl, FormLabel, Heading,
  IconButton, Input, InputGroup, InputRightElement, Spinner, Text, VStack,
} from '@chakra-ui/react';
import { useEffect, useState, type FormEvent } from 'react';
import { MdArrowBack, MdVisibility, MdVisibilityOff } from 'react-icons/md';
import { getSession, login, logout, type AdminSession } from '../../lib/auth';
import { API_BASE_URL } from '../../lib/api';

// Adapted from the HaUI login form, retaining its layout and Chakra styling.
export default function LoginPage() {
  const [session, setSession] = useState<AdminSession | null>(null);
  const [checking, setChecking] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    document.title = 'YZU Student Assistant — Administrator login';
    getSession().then(setSession).catch(() => setError('Unable to check your session. Is the backend running?'))
      .finally(() => setChecking(false));
  }, []);

  useEffect(() => {
    if (!session) return;
    const timer = window.setTimeout(() => {
      setSession(null);
      setError('Your session has expired. Please log in again.');
    }, Math.max(0, session.expires_at * 1000 - Date.now()));
    return () => window.clearTimeout(timer);
  }, [session]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    setIsSubmitting(true);
    setError('');
    try {
      setSession(await login(String(values.get('username')), String(values.get('password'))));
      form.reset();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Login failed.');
    } finally { setIsSubmitting(false); }
  }

  async function handleLogout() {
    setIsSubmitting(true);
    setError('');
    try { await logout(); setSession(null); }
    catch { setError('Logout failed. Please try again.'); }
    finally { setIsSubmitting(false); }
  }

  return (
    <Container maxW="container.sm" py={10}>
      <VStack spacing={8} align="stretch">
        <Box textAlign="center">
          <Heading size="lg">Administrator login</Heading>
          <Text mt={2} color="gray.600">Sign in to manage YZU documents</Text>
        </Box>
        {error && <Alert status="error"><AlertIcon />{error}</Alert>}
        {checking ? <Spinner alignSelf="center" aria-label="Checking session" /> : session ? (
          <VStack spacing={4} align="stretch">
            <Alert status="success"><AlertIcon />Signed in as {session.username}</Alert>
            <Text>Your administrator session is active. Document upload is not available yet.</Text>
            <Button as="a" href={`${API_BASE_URL}/docs`} colorScheme="blue">Open API documentation</Button>
            <Button onClick={handleLogout} isLoading={isSubmitting} variant="outline">Log out</Button>
          </VStack>
        ) : (
          <Box as="form" onSubmit={handleSubmit}>
            <VStack spacing={4}>
              <FormControl isRequired>
                <FormLabel htmlFor="username">Username</FormLabel>
                <Input id="username" name="username" placeholder="Enter your username"
                  autoComplete="username" isDisabled={isSubmitting} />
              </FormControl>
              <FormControl isRequired>
                <FormLabel htmlFor="password">Password</FormLabel>
                <InputGroup>
                  <Input id="password" name="password" type={showPassword ? 'text' : 'password'}
                    placeholder="Enter your password" autoComplete="current-password"
                    maxLength={1024} isDisabled={isSubmitting} />
                  <InputRightElement>
                    <IconButton type="button" aria-label={showPassword ? 'Hide password' : 'Show password'}
                      icon={showPassword ? <MdVisibilityOff /> : <MdVisibility />}
                      variant="ghost" onClick={() => setShowPassword(!showPassword)}
                      isDisabled={isSubmitting} />
                  </InputRightElement>
                </InputGroup>
              </FormControl>
              <Button type="submit" colorScheme="blue" width="100%" isLoading={isSubmitting}
                loadingText="Signing in...">Log in</Button>
            </VStack>
          </Box>
        )}
        <Button as="a" href="/" variant="outline" colorScheme="gray" width="100%" leftIcon={<MdArrowBack />}
          isDisabled={isSubmitting}>Back to student chat</Button>
      </VStack>
    </Container>
  );
}
