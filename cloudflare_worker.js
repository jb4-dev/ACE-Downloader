/**
 * Cloudflare Worker Script to Proxy API, Image, and Autocomplete Requests
 * Domain is Base64 encoded to avoid having plaintext in the script.
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Standard CORS headers for all responses
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, HEAD, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    // Handle CORS preflight requests
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    // Route requests
    if (url.pathname === '/api') {
      return handleApiRequest(request, corsHeaders);
    }

    if (url.pathname === '/image') {
      return handleImageRequest(request, corsHeaders);
    }
    
    // New route for autocomplete
    if (url.pathname === '/autocomplete') {
        return handleAutocompleteRequest(request, corsHeaders);
    }

    return new Response(getLandingPage(), {
      status: 200,
      headers: { 'Content-Type': 'text/html' },
    });
  },
};

/**
 * Decodes a Base64-encoded string.
 */
function decodeBase64(str) {
  return atob(str);
}

/**
 * Handles API requests by forwarding them to the target API.
 */
async function handleApiRequest(request, corsHeaders) {
  const url = new URL(request.url);

  // Base64 for "website"
  const encodedDomain = "YXBpLnJ1bGUzNC54eHg=";
  const targetDomain = decodeBase64(encodedDomain);

  const targetApiUrl = `https://${targetDomain}/index.php?page=dapi&s=post&q=index${url.search}`;
  
  try {
    const response = await fetch(targetApiUrl, {
      method: request.method,
      headers: request.headers,
    });

    const newResponse = new Response(response.body, response);
    for (const [key, value] of Object.entries(corsHeaders)) {
      newResponse.headers.set(key, value);
    }
    return newResponse;

  } catch (e) {
    return new Response(`Error fetching from the API endpoint: ${e.message}`, { status: 502, headers: corsHeaders });
  }
}

/**
 * Handles image download requests by fetching from the source and streaming it.
 */
async function handleImageRequest(request, corsHeaders) {
  const url = new URL(request.url);
  const imageUrl = url.searchParams.get('url');

  if (!imageUrl) {
    return new Response('Error: The "url" query parameter is missing.', { status: 400, headers: corsHeaders });
  }
  
  try {
    const response = await fetch(imageUrl);

    if (!response.ok) {
      return new Response(`Failed to fetch the image. Status: ${response.status}`, {
        status: response.status,
        headers: corsHeaders,
      });
    }

    const newResponse = new Response(response.body, response);
    for (const [key, value] of Object.entries(corsHeaders)) {
      newResponse.headers.set(key, value);
    }
    
    return newResponse;

  } catch (e) {
    return new Response(`Error fetching the image file: ${e.message}`, { status: 502, headers: corsHeaders });
  }
}

/**
 * Handles autocomplete requests.
 */
async function handleAutocompleteRequest(request, corsHeaders) {
  const url = new URL(request.url);
  const query = url.searchParams.get('q');

  if (!query) {
    return new Response('Error: The "q" query parameter is missing.', { status: 400, headers: corsHeaders });
  }

  // Base64 for "website"
  const encodedDomain = "YXBpLnJ1bGUzNC54eHg=";
  const targetDomain = decodeBase64(encodedDomain);
  const targetAutocompleteUrl = `https://${targetDomain}/autocomplete.php?q=${encodeURIComponent(query)}`;

  try {
    const response = await fetch(targetAutocompleteUrl);
    
    const newResponse = new Response(response.body, response);
    for (const [key, value] of Object.entries(corsHeaders)) {
      newResponse.headers.set(key, value);
    }
    newResponse.headers.set('Content-Type', 'application/json');
    return newResponse;

  } catch (e) {
    return new Response(`Error fetching autocomplete data: ${e.message}`, { status: 502, headers: corsHeaders });
  }
}


function getLandingPage() {
  return `
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>M3 Proxy</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; background-color: #f3f4f6; color: #111827; margin: 0; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
            .container { max-width: 600px; background: #fff; padding: 2rem; border-radius: 0.75rem; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1); text-align: center; }
            h1 { font-size: 1.875rem; color: #1f2937; margin-bottom: 0.5rem; }
            p { color: #4b5563; }
            code { background-color: #e5e7eb; padding: 0.2rem 0.4rem; border-radius: 0.25rem; font-family: "Courier New", Courier, monospace; }
            .example { margin-top: 1.5rem; font-size: 0.9rem; }
            .note { color: #991b1b; background-color: #fef2f2; padding: 1rem; border-radius: 0.5rem; margin-top: 1.5rem; text-align: left; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>M3 Proxy</h1>
            <p>©2025 PGN.</p>
            <div class="example">
                <p>Proxy for API, image, and autocomplete endpoints.</p>
                <p><code>/api</code>, <code>/image</code>, and <code>/autocomplete</code> are used.</p>
            </div>
            <div class="note">
                <strong>Note:</strong> API (excluding auto-complete) has limit of 60 req/60 sec.
            </div>
        </div>
    </body>
    </html>
  `;
}
