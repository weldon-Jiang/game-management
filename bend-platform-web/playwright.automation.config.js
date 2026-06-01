import baseConfig from './playwright.config.js'

export default {
  ...baseConfig,
  webServer: undefined,
  use: {
    ...baseConfig.use,
    baseURL: 'http://localhost:3090'
  }
}
