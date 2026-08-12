export async function onRequest(context) {
  const { request, env, next } = context;
  const url = new URL(request.url);

  // 1. Skip password check for static assets (images, js, css, etc.)
  const pathname = url.pathname;
  if (
    pathname.startsWith('/_next/') ||
    pathname.startsWith('/static/') ||
    pathname.match(/\.(ico|png|jpg|jpeg|svg|webp|gif|woff|woff2|ttf|css|js|map)$/)
  ) {
    return next();
  }

  // 2. Get the password from Cloudflare Environment Variables
  const EXPECTED_PASSWORD = env.SITE_PASSWORD || 'default_secret';

  // 3. Check if already authenticated via cookie
  const cookieHeader = request.headers.get('Cookie') || '';
  if (cookieHeader.includes('auth_token=true')) {
    return next();
  }

  // 4. Handle password form submission (POST)
  let isError = false;
  if (request.method === 'POST') {
    try {
      const contentType = request.headers.get('content-type') || '';
      let submittedPassword = null;

      if (contentType.includes('application/x-www-form-urlencoded') || contentType.includes('multipart/form-data')) {
        const formData = await request.formData();
        submittedPassword = formData.get('password');
      }

      if (submittedPassword === EXPECTED_PASSWORD) {
        // Correct password — set cookie and redirect to GET
        const maxAge = 60 * 60 * 24 * 30; // 30 days
        return new Response(null, {
          status: 302,
          headers: {
            'Location': pathname || '/',
            'Set-Cookie': `auth_token=true; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAge}`,
          },
        });
      } else {
        isError = true;
      }
    } catch (e) {
      isError = true;
    }
  }

  // 5. Show the password page
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Restricted Access</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
      display: flex; justify-content: center; align-items: center;
      min-height: 100vh; background: #0f0f11; color: #fff;
    }
    .card {
      background: #18181b; border: 1px solid #27272a;
      border-radius: 16px; padding: 2.5rem 2rem;
      box-shadow: 0 25px 60px rgba(0,0,0,0.6);
      width: 90%; max-width: 380px; text-align: center;
    }
    .lock { font-size: 2.5rem; margin-bottom: 1rem; }
    h1 { font-size: 1.3rem; font-weight: 600; margin-bottom: 0.4rem; }
    p { color: #71717a; font-size: 0.875rem; margin-bottom: 1.5rem; }
    .error {
      background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3);
      color: #f87171; border-radius: 8px; padding: 0.6rem 0.75rem;
      font-size: 0.85rem; margin-bottom: 1rem;
    }
    input[type=password] {
      display: block; width: 100%; padding: 0.75rem 1rem;
      border-radius: 8px; border: 1px solid #27272a;
      background: #09090b; color: #fff; font-size: 1rem;
      margin-bottom: 0.75rem; transition: border-color 0.2s, box-shadow 0.2s;
    }
    input[type=password]:focus {
      outline: none; border-color: #3b82f6;
      box-shadow: 0 0 0 3px rgba(59,130,246,0.2);
    }
    button {
      display: block; width: 100%; padding: 0.75rem 1rem;
      background: #3b82f6; color: #fff; border: none;
      border-radius: 8px; font-size: 1rem; font-weight: 600;
      cursor: pointer; transition: background 0.15s, transform 0.1s;
    }
    button:hover { background: #2563eb; }
    button:active { transform: scale(0.98); }
  </style>
</head>
<body>
  <div class="card">
    <div class="lock">🔒</div>
    <h1>Protected Access</h1>
    <p>This environment is private. Enter the password to continue.</p>
    ${isError ? '<div class="error">Incorrect password. Please try again.</div>' : ''}
    <form method="POST" action="${pathname}">
      <input type="password" name="password" placeholder="Enter password" required autofocus />
      <button type="submit">Unlock</button>
    </form>
  </div>
</body>
</html>`;

  return new Response(html, {
    status: 401,
    headers: { 'Content-Type': 'text/html; charset=utf-8' },
  });
}
