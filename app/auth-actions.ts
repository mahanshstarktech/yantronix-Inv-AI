'use server';

import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';

const AUTH_COOKIE = 'auth_token';
const COOKIE_MAX_AGE = 60 * 60 * 24 * 30; // 30 days

export async function checkAuth(): Promise<boolean> {
  const cookieStore = await cookies();
  return cookieStore.get(AUTH_COOKIE)?.value === 'true';
}

export async function loginAction(formData: FormData) {
  const password = formData.get('password') as string;
  const expected = process.env.SITE_PASSWORD || 'default_secret';

  if (password === expected) {
    const cookieStore = await cookies();
    cookieStore.set(AUTH_COOKIE, 'true', {
      path: '/',
      httpOnly: true,
      secure: true,
      sameSite: 'lax',
      maxAge: COOKIE_MAX_AGE,
    });
    redirect('/');
  }

  // Wrong password - redirect back with error flag
  redirect('/?auth_error=1');
}
