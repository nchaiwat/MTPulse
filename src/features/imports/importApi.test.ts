import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MANUAL_UPLOAD_LIMITS, previewHpMhImport, previewImport } from './importApi'

class FakeEventTarget {
  private listeners = new Map<string, EventListener[]>()

  addEventListener(type: string, listener: EventListenerOrEventListenerObject | null) {
    if (typeof listener !== 'function') return
    const listeners = this.listeners.get(type) ?? []
    listeners.push(listener)
    this.listeners.set(type, listeners)
  }

  emit(type: string, event: Event) {
    this.listeners.get(type)?.forEach((listener) => listener(event))
  }
}

class FakeXMLHttpRequest extends FakeEventTarget {
  static instances: FakeXMLHttpRequest[] = []
  upload = new FakeEventTarget()
  status = 0
  responseText = ''
  method = ''
  url = ''
  body: Document | XMLHttpRequestBodyInit | null = null

  constructor() {
    super()
    FakeXMLHttpRequest.instances.push(this)
  }

  open(method: string, url: string) {
    this.method = method
    this.url = url
  }

  send(body: Document | XMLHttpRequestBodyInit | null) {
    this.body = body
  }
}

describe('manual import upload transport', () => {
  beforeEach(() => {
    FakeXMLHttpRequest.instances = []
    vi.stubGlobal('XMLHttpRequest', FakeXMLHttpRequest)
  })

  afterEach(() => vi.unstubAllGlobals())

  it('reports byte upload progress then processing before resolving', async () => {
    const progress = vi.fn()
    const request = previewImport(
      new File(['raw'], 'twd.xls', { type: 'application/vnd.ms-excel' }),
      progress,
    )
    const xhr = FakeXMLHttpRequest.instances[0]

    xhr.upload.emit(
      'progress',
      new ProgressEvent('progress', {
        lengthComputable: true,
        loaded: 50,
        total: 100,
      }),
    )
    xhr.upload.emit('load', new Event('load'))
    xhr.status = 200
    xhr.responseText = JSON.stringify({ detectedMt: 'TWD' })
    xhr.emit('load', new Event('load'))

    await expect(request).resolves.toMatchObject({ detectedMt: 'TWD' })
    expect(progress).toHaveBeenNthCalledWith(1, {
      phase: 'uploading',
      loaded: 50,
      total: 100,
      percent: 50,
    })
    expect(progress).toHaveBeenNthCalledWith(2, {
      phase: 'processing',
      loaded: 0,
      total: 0,
      percent: 100,
    })
    expect(xhr.method).toBe('POST')
    expect(xhr.url).toContain('/api/imports/preview')
    expect(xhr.body).toBeInstanceOf(FormData)
  })

  it('returns the API detail when upload validation fails', async () => {
    const request = previewImport(new File(['bad'], 'bad.xls'))
    const xhr = FakeXMLHttpRequest.instances[0]
    xhr.status = 400
    xhr.responseText = JSON.stringify({ detail: 'ตรวจสอบไฟล์ไม่ผ่าน' })
    xhr.emit('load', new Event('load'))

    await expect(request).rejects.toThrow('ตรวจสอบไฟล์ไม่ผ่าน')
  })

  it('sends the HP/MH inventory and sales pair to the dedicated preview endpoint', async () => {
    const inventory = new File(['inventory'], 'Inventory.zip')
    const sales = new File(['sales'], 'Sales.zip')
    const request = previewHpMhImport(inventory, sales)
    const xhr = FakeXMLHttpRequest.instances[0]
    const body = xhr.body as FormData

    expect(xhr.url).toContain('/api/imports/hp-mh/preview')
    expect(body.get('inventory_file')).toBe(inventory)
    expect(body.get('sales_file')).toBe(sales)

    xhr.status = 200
    xhr.responseText = JSON.stringify({ detectedSourceGroup: 'HP_MH' })
    xhr.emit('load', new Event('load'))
    await expect(request).resolves.toMatchObject({ detectedSourceGroup: 'HP_MH' })
  })

  it('rejects instead of hanging when a successful response is not valid JSON', async () => {
    const request = previewImport(new File(['raw'], 'twd.xls'))
    const xhr = FakeXMLHttpRequest.instances[0]
    xhr.status = 200
    xhr.responseText = '<html>unexpected proxy response</html>'
    xhr.emit('load', new Event('load'))

    await expect(request).rejects.toThrow('Import API ส่งข้อมูลตอบกลับไม่ถูกต้อง')
  })
})

describe('manual folder upload phase 1 contract', () => {
  it('publishes the approved limits without changing the active UI', () => {
    expect(MANUAL_UPLOAD_LIMITS).toEqual({
      maxFolderFiles: 200,
      maxFileBytes: 25 * 1024 * 1024,
      uploadConcurrency: 3,
      stagingRetentionDays: 7,
    })
  })
})
