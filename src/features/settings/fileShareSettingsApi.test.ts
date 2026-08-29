import { afterEach, describe, expect, it, vi } from 'vitest'
import { saveFileShareSettings, testFileShare } from './fileShareSettingsApi'

const input = {
  baseUnc: '\\\\WA-NAS-IT03\\FileShare-2\\SaleOut_RPT',
  domain: 'IT-ADMIN',
  username: 'svc-mtpulse',
  password: 'secret',
  profiles: [{
    code: 'TWD',
    name: 'Thai Watsadu',
    subfolder: 'TWD',
    enabled: true,
    fullPath: '',
  }],
}

describe('fileShareSettingsApi', () => {
  afterEach(() => vi.restoreAllMocks())

  it('saves the shared account and per-MT subfolder', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        baseUnc: input.baseUnc,
        domain: input.domain,
        username: input.username,
        passwordConfigured: true,
        passwordMasked: '********',
        lastTestAt: null,
        lastTestStatus: null,
        lastTestResults: [],
        profiles: input.profiles,
      }), { status: 200 }),
    )

    await saveFileShareSettings(input)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/fileshare-settings'),
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          base_unc: input.baseUnc,
          domain: input.domain,
          username: input.username,
          password: input.password,
          profiles: [{ code: 'TWD', subfolder: 'TWD', enabled: true }],
        }),
      }),
    )
  })

  it('tests the draft settings without importing files', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        status: 'success',
        message: 'เข้าถึง FileShare ได้',
        results: [],
      }), { status: 200 }),
    )

    await testFileShare(input)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/fileshare-settings/test'),
      expect.objectContaining({ method: 'POST' }),
    )
  })
})
