import { API_BASE_URL } from './api';

export type AdminSession = { username: string; expires_at: number };

async function authRequest(path: string, options: RequestInit = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    credentials: 'include',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Protection': '1' },
  });
  if (!response.ok) {
    const message = response.status === 401
      ? 'Incorrect credentials or your session has expired.'
      : response.status === 503
        ? 'Administrator setup is incomplete. Configure the password and restart the backend.'
        : 'Unable to complete the request. Please try again.';
    throw new Error(message);
  }
  return response;
}

export async function login(username: string, password: string): Promise<AdminSession> {
  const response = await authRequest('/auth/token', {
    method: 'POST', body: JSON.stringify({ username, password }),
  });
  return response.json();
}

export async function getSession(): Promise<AdminSession | null> {
  const response = await fetch(`${API_BASE_URL}/admin/session`, {
    credentials: 'include', cache: 'no-store',
  });
  if (response.status === 401) return null;
  if (!response.ok) throw new Error('Unable to check your administrator session.');
  return response.json();
}

export async function logout(): Promise<void> {
  await authRequest('/auth/logout', { method: 'POST' });
}
