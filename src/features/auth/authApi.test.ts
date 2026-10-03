import { afterEach, expect, it, vi } from 'vitest'
import { apiFetch, applyXhrAuth, setSessionToken } from './authApi'
afterEach(() => { setSessionToken(''); vi.unstubAllGlobals() })
it('attaches CSRF to mutations and signals expired sessions', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ status: 401 })
  vi.stubGlobal('fetch', fetchMock)
  const expired = vi.fn()
  window.addEventListener('mtpulse:unauthorized', expired)
  setSessionToken('csrf-test')
  await apiFetch('/api/item-mappings/import', { method: 'POST', body: new FormData() })
  expect(fetchMock.mock.calls[0][1].headers.get('X-CSRF-Token')).toBe('csrf-test')
  expect(fetchMock.mock.calls[0][1].credentials).toBe('include')
  expect(expired).toHaveBeenCalledOnce()
  window.removeEventListener('mtpulse:unauthorized', expired)
})

it('attaches authentication to upload requests without changing multipart content type', () => {
  const xhr = { withCredentials: false, setRequestHeader: vi.fn() }
  setSessionToken('upload-csrf')
  applyXhrAuth(xhr as unknown as XMLHttpRequest)
  expect(xhr.withCredentials).toBe(true)
  expect(xhr.setRequestHeader).toHaveBeenCalledExactlyOnceWith('X-CSRF-Token', 'upload-csrf')
})
