export const onRequest: PagesFunction<{ SITE_PASSWORD: string }> = async (context) => {
  const { request, env, next } = context;
  const url = new URL(request.url);

  // 1. Get the password from Cloudflare Environment Variables
  const EXPECTED_PASSWORD = env.SITE_PASSWORD || 'default_secret';

  // 2. Check if the user is submitting a password via POST
  if (request.method === 'POST') {
    const formData = await request.formData();
    const submittedPassword = formData.get('password');

    if (submittedPassword === EXPECTED_PASSWORD) {
      // Password is correct, set a cookie for 30 days and redirect to the same page
      const response = new Response(null, {
        status: 302,
        headers: {
          'Location': url.pathname,
          'Set-Cookie': `auth_token=true; Path=/; HttpOnly; Secure; Max-Age=${60 * 60 * 24 * 30}`,
        },
      });
      return response;
    }
  }

  // 3. Check if the user already has the auth cookie
  const cookieHeader = request.headers.get('Cookie');
  if (cookieHeader && cookieHeader.includes('auth_token=true')) {
    // They are authenticated, let them through to the actual site
    return next();
  }

  // 4. If not authenticated (or wrong password), return the Password Page
  const isError = request.method === 'POST';
  
  return new Response(`
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Restricted Access</title>
      <style>
        body { font-family: system-ui, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #111; color: #fff; margin: 0; }
        .container { text-align: center; background: #222; padding: 2.5rem 2rem; border-radius: 12px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5); border: 1px solid #333; max-width: 400px; width: 100%; box-sizing: border-box; }
        input { padding: 0.75rem; border-radius: 6px; border: 1px solid #444; background: #111; color: white; margin-bottom: 1rem; width: 100%; box-sizing: border-box; font-size: 1rem; }
        input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3); }
        button { background: #3b82f6; color: white; border: none; padding: 0.75rem 1rem; border-radius: 6px; cursor: pointer; width: 100%; font-weight: 600; font-size: 1rem; transition: background 0.2s; }
        button:hover { background: #2563eb; }
        .error { color: #ef4444; margin-bottom: 1rem; font-size: 0.9rem; font-weight: 500; }
      </style>
    </head>
    <body>
      <div class="container">
        <h2 style="margin-top: 0; margin-bottom: 0.5rem;">Protected Environment</h2>
        <p style="color: #aaa; margin-bottom: 1.5rem; font-size: 0.95rem;">Please enter the password to access this site.</p>
        
        ${isError ? '<div class="error">Incorrect password. Please try again.</div>' : ''}
        
        <form method="POST">
          <input type="password" name="password" placeholder="Enter Password" required autofocus />
          <button type="submit">Unlock</button>
        </form>
      </div>
    </body>
    </html>
  `, {
    headers: { 'Content-Type': 'text/html' }
  });
};
