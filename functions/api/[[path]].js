export async function onRequest(context) {
  const url = new URL(context.request.url);
  const backendUrl = `https://backend-bitter-paper-5548.fly.dev${url.pathname}${url.search}`;

  const headers = new Headers(context.request.headers);
  headers.delete('host');

  const response = await fetch(backendUrl, {
    method: context.request.method,
    headers,
    body: ['GET', 'HEAD'].includes(context.request.method) ? undefined : context.request.body,
    redirect: 'manual',
  });

  const outHeaders = new Headers(response.headers);
  outHeaders.set('access-control-allow-origin', '*');

  return new Response(response.body, {
    status: response.status,
    headers: outHeaders,
  });
}
