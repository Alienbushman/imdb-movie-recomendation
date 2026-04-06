// Pass-through proxy: client includes /v1 in its baseURL (/api/v1),
// so the proxy just forwards /api/* → backend /api/* unchanged.
export default defineEventHandler(async (event) => {
  const backend = process.env.API_BACKEND || 'http://localhost:8562'
  const path = event.context.params?.path || ''
  const queryString = getRequestURL(event).search
  const target = `${backend}/api/${path}${queryString}`

  try {
    return await proxyRequest(event, target, {
      fetchOptions: { signal: AbortSignal.timeout(20 * 60 * 1000) }, // 20 min
    })
  } catch {
    setResponseStatus(event, 502)
    return { detail: 'Backend unavailable' }
  }
})
