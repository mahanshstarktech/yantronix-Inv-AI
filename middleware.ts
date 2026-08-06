import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Required for Cloudflare Pages (next-on-pages adapter)
export const runtime = 'edge';

export async function middleware(request: NextRequest) {
  const url = request.nextUrl;

  // Get the password from Cloudflare Environment Variables
  const EXPECTED_PASSWORD = process.env.SITE_PASSWORD || 'default_secret';

  // 1. Check if the user already has the auth cookie - let them through immediately
  const authCookie = request.cookies.get('auth_token');
  if (authCookie && authCookie.value === 'true') {
    return NextResponse.next();
  }

  // 2. Check if the user is submitting a password via POST
  let isError = false;
  if (request.method === 'POST') {
    try {
      const formData = await request.formData();
      const submittedPassword = formData.get('password');

      if (submittedPassword === EXPECTED_PASSWORD) {
        // Password is correct - redirect to homepage with auth cookie set
        const response = NextResponse.redirect(new URL('/', request.url));
        response.cookies.set('auth_token', 'true', {
          path: '/',
          httpOnly: true,
          secure: true,
          sameSite: 'lax',
          maxAge: 60 * 60 * 24 * 30, // 30 days
        });
        return response;
      } else {
        isError = true;
      }
    } catch (_e) {
      isError = true;
    }
  }

  // 3. Not authenticated - show the password page
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Restricted Access</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    body { font-family: system-ui, -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #0f0f10; color: #fff; margin: 0; }
    .container { text-align: center; background: #1a1a1e; padding: 2.5rem 2rem; border-radius: 16px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7); border: 1px solid #2a2a2e; max-width: 380px; width: 90%; }
    h2 { margin: 0 0 0.5rem 0; font-size: 1.4rem; font-weight: 600; }
    p { color: #888; margin: 0 0 1.5rem 0; font-size: 0.9rem; }
    .error { color: #f87171; margin-bottom: 1rem; font-size: 0.85rem; background: rgba(248,113,113,0.1); border: 1px solid rgba(248,113,113,0.2); padding: 0.5rem; border-radius: 6px; }
    input[type=password] { display: block; padding: 0.75rem 1rem; border-radius: 8px; border: 1px solid #2a2a2e; background: #0f0f10; color: white; margin-bottom: 0.75rem; width: 100%; font-size: 1rem; transition: border-color 0.2s, box-shadow 0.2s; }
    input[type=password]:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2); }
    button { background: #3b82f6; color: white; border: none; padding: 0.75rem 1rem; border-radius: 8px; cursor: pointer; width: 100%; font-weight: 600; font-size: 1rem; transition: background 0.2s, transform 0.1s; }
    button:hover { background: #2563eb; }
    button:active { transform: scale(0.98); }
  </style>
</head>
<body>
  <div class="container">
    <h2>🔒 Protected Environment</h2>
    <p>Please enter the password to continue.</p>
    ${isError ? '<div class="error">Incorrect password. Please try again.</div>' : ''}
    <form method="POST">
      <input type="password" name="password" placeholder="Password" required autofocus />
      <button type="submit">Unlock Access</button>
    </form>
  </div>
</body>
</html>`;

  return new Response(html, {
    status: 401,
    headers: { 'Content-Type': 'text/html; charset=utf-8' },
  });
}

// Match ALL routes except Next.js internals and static files
export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
