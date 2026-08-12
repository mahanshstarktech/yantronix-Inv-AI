import "./lib/error-capture";

import { consumeLastCapturedError } from "./lib/error-capture";
import { renderErrorPage } from "./lib/error-page";

type ServerEntry = {
  fetch: (request: Request, env: unknown, ctx: unknown) => Promise<Response> | Response;
};

let serverEntryPromise: Promise<ServerEntry> | undefined;

async function getServerEntry(): Promise<ServerEntry> {
  if (!serverEntryPromise) {
    serverEntryPromise = import("@tanstack/react-start/server-entry").then(
      (m) => (m.default ?? m) as ServerEntry,
    );
  }
  return serverEntryPromise;
}

// ── Password Gate ─────────────────────────────────────────────────────────────
// Intercepts EVERY request before TanStack Start runs.
// Password is read from the Cloudflare env variable SITE_PASSWORD.
// Once correct, a cookie is set for 30 days.

const AUTH_COOKIE_NAME = "lzc_auth";
const AUTH_COOKIE_MAX_AGE = 60 * 60 * 24 * 30; // 30 days

function isAuthenticated(request: Request): boolean {
  const cookie = request.headers.get("Cookie") || "";
  return cookie.includes(`${AUTH_COOKIE_NAME}=authenticated`);
}

function isStaticAsset(pathname: string): boolean {
  return /\.(js|css|map|ico|png|jpg|jpeg|svg|webp|gif|woff2?|ttf|eot|json)$/i.test(pathname);
}

function renderLoginPage(isError: boolean): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LazECommerce — Login</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', system-ui, sans-serif;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: oklch(0.145 0.005 285);
      color: oklch(0.96 0.003 285);
    }
    .gate {
      width: 90%;
      max-width: 400px;
      text-align: center;
    }
    .logo-row {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.6rem;
      margin-bottom: 2rem;
    }
    .logo-dot {
      width: 36px; height: 36px;
      border-radius: 10px;
      background: oklch(0.745 0.17 162);
      display: flex; align-items: center; justify-content: center;
      font-weight: 700; font-size: 1.1rem;
      color: oklch(0.145 0.005 285);
    }
    .logo-text {
      font-size: 1.25rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }
    .card {
      background: oklch(0.19 0.006 285);
      border: 1px solid oklch(0.28 0.008 285);
      border-radius: 16px;
      padding: 2.5rem 2rem 2rem;
    }
    .lock-icon {
      width: 48px; height: 48px;
      border-radius: 12px;
      background: oklch(0.23 0.008 285);
      display: flex; align-items: center; justify-content: center;
      margin: 0 auto 1.25rem;
      font-size: 1.5rem;
    }
    h1 { font-size: 1.2rem; font-weight: 600; margin-bottom: 0.35rem; }
    .subtitle {
      color: oklch(0.65 0.01 285);
      font-size: 0.85rem;
      margin-bottom: 1.5rem;
      line-height: 1.5;
    }
    .error-box {
      background: rgba(239,68,68,0.08);
      border: 1px solid rgba(239,68,68,0.25);
      color: oklch(0.7 0.18 25);
      border-radius: 8px;
      padding: 0.6rem 0.85rem;
      font-size: 0.82rem;
      margin-bottom: 1rem;
      font-weight: 500;
    }
    label {
      display: block;
      text-align: left;
      font-size: 0.78rem;
      font-weight: 500;
      color: oklch(0.75 0.008 285);
      margin-bottom: 0.4rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    input[type=password] {
      display: block;
      width: 100%;
      padding: 0.7rem 0.85rem;
      border-radius: 8px;
      border: 1px solid oklch(0.28 0.008 285);
      background: oklch(0.145 0.005 285);
      color: oklch(0.96 0.003 285);
      font-family: 'Inter', system-ui, sans-serif;
      font-size: 0.95rem;
      margin-bottom: 1rem;
      transition: border-color 0.2s, box-shadow 0.2s;
      outline: none;
    }
    input[type=password]:focus {
      border-color: oklch(0.745 0.17 162);
      box-shadow: 0 0 0 3px oklch(0.745 0.17 162 / 0.15);
    }
    button[type=submit] {
      display: block;
      width: 100%;
      padding: 0.7rem 1rem;
      background: oklch(0.745 0.17 162);
      color: oklch(0.145 0.005 285);
      border: none;
      border-radius: 8px;
      font-family: 'Inter', system-ui, sans-serif;
      font-size: 0.95rem;
      font-weight: 600;
      cursor: pointer;
      transition: filter 0.15s, transform 0.1s;
    }
    button[type=submit]:hover { filter: brightness(1.1); }
    button[type=submit]:active { transform: scale(0.98); }
    .footer {
      margin-top: 1.5rem;
      font-size: 0.75rem;
      color: oklch(0.45 0.008 285);
    }
  </style>
</head>
<body>
  <div class="gate">
    <div class="logo-row">
      <div class="logo-dot">L</div>
      <div class="logo-text">LazECommerce</div>
    </div>
    <div class="card">
      <div class="lock-icon">🔒</div>
      <h1>Welcome Back</h1>
      <p class="subtitle">This is a private environment. Please enter your access password to continue.</p>
      ${isError ? '<div class="error-box">Incorrect password. Please try again.</div>' : ''}
      <form method="POST" action="/__auth">
        <label for="password">Access Password</label>
        <input type="password" id="password" name="password" placeholder="Enter your password" required autofocus />
        <button type="submit">Unlock Access</button>
      </form>
    </div>
    <p class="footer">Protected by LazECommerce Auth</p>
  </div>
</body>
</html>`;
}
// ── Site password — change this string to update the password ──────────────
const SITE_PASSWORD = "getThisShitDone";

async function handleAuthRequest(
  request: Request,
): Promise<Response | null> {
  const url = new URL(request.url);
  const pathname = url.pathname;

  // Always allow static assets through (CSS, JS, images, fonts, etc.)
  if (isStaticAsset(pathname) || pathname.startsWith("/_build")) {
    return null; // null = let the app handle it
  }

  // Handle POST to /__auth (password form submission)
  if (request.method === "POST" && pathname === "/__auth") {
    try {
      const formData = await request.formData();
      const submittedPassword = formData.get("password") as string;

      if (submittedPassword === SITE_PASSWORD) {
        // Correct — set cookie and redirect to home
        return new Response(null, {
          status: 302,
          headers: {
            Location: "/",
            "Set-Cookie": `${AUTH_COOKIE_NAME}=authenticated; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${AUTH_COOKIE_MAX_AGE}`,
          },
        });
      }
    } catch (_e) {
      // fall through to error login page
    }

    // Wrong password
    return new Response(renderLoginPage(true), {
      status: 401,
      headers: { "Content-Type": "text/html; charset=utf-8" },
    });
  }

  // Check auth cookie
  if (isAuthenticated(request)) {
    return null; // Authenticated — let the app handle it
  }

  // Not authenticated — show login page
  return new Response(renderLoginPage(false), {
    status: 401,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

// h3 swallows in-handler throws into a normal 500 Response with body
// {"unhandled":true,"message":"HTTPError"} — try/catch alone never fires for those.
async function normalizeCatastrophicSsrResponse(response: Response): Promise<Response> {
  if (response.status < 500) return response;
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) return response;

  const body = await response.clone().text();
  if (!body.includes('"unhandled":true') || !body.includes('"message":"HTTPError"')) {
    return response;
  }

  console.error(consumeLastCapturedError() ?? new Error(`h3 swallowed SSR error: ${body}`));
  return new Response(renderErrorPage(), {
    status: 500,
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}

export default {
  async fetch(request: Request, env: unknown, ctx: unknown) {
    try {
      // ── Auth gate — runs BEFORE everything else ──────────────────────
      const authResponse = await handleAuthRequest(request);
      if (authResponse) return authResponse;

      // ── Normal app flow ──────────────────────────────────────────────
      const handler = await getServerEntry();
      const response = await handler.fetch(request, env, ctx);
      return await normalizeCatastrophicSsrResponse(response);
    } catch (error) {
      console.error(error);
      return new Response(renderErrorPage(), {
        status: 500,
        headers: { "content-type": "text/html; charset=utf-8" },
      });
    }
  },
};
