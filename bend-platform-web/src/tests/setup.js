import { beforeAll, afterAll, afterEach, vi } from 'vitest'
import { cleanup } from '@vue/test-utils'
import { server } from './mocks/server.js'

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' })
})

afterAll(() => {
  server.close()
})

afterEach(() => {
  server.resetHandlers()
  cleanup()
})

global.XMLHttpRequest = jest.mock ? undefined : window.XMLHttpRequest
