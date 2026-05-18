let stompClient = null
let connectionPromise = null

export const getStompClient = () => {
  return stompClient
}

export const connectStomp = () => {
  return new Promise((resolve, reject) => {
    const Stomp = window.StompJs
    
    if (!Stomp) {
      reject(new Error('Stomp库未加载'))
      return
    }

    if (stompClient && stompClient.connected) {
      resolve(stompClient)
      return
    }

    if (connectionPromise) {
      connectionPromise.then(resolve).catch(reject)
      return
    }

    const envBaseUrl = import.meta.env.VITE_API_BASE_URL
    const apiBaseUrl = (envBaseUrl && envBaseUrl !== '/' && envBaseUrl.startsWith('http')) 
      ? envBaseUrl 
      : window.location.origin
    const protocol = apiBaseUrl.startsWith('https') ? 'wss:' : 'ws:'
    const host = new URL(apiBaseUrl).host
    const wsUrl = `${protocol}//${host}/ws/stomp`

    stompClient = new Stomp.Client({
      brokerURL: wsUrl,
      reconnectDelay: 5000,
      heartbeatIncoming: 30000,
      heartbeatOutgoing: 30000
    })

    stompClient.onConnect = () => {
      console.log('WebSocket connected successfully')
      connectionPromise = null
      resolve(stompClient)
    }

    stompClient.onStompError = (frame) => {
      console.error('WebSocket STOMP error:', frame)
      connectionPromise = null
      reject(new Error('STOMP协议错误'))
    }

    stompClient.onWebSocketError = (error) => {
      console.error('WebSocket connection error:', error)
      connectionPromise = null
      reject(new Error('网络连接错误'))
    }

    stompClient.onDisconnect = () => {
      console.log('WebSocket disconnected')
      stompClient = null
      connectionPromise = null
    }

    connectionPromise = new Promise((res, rej) => {
      stompClient.activate()
      setTimeout(() => {
        if (!stompClient?.connected) {
          rej(new Error('连接超时'))
          connectionPromise = null
        }
      }, 10000)
    })
  })
}

export const disconnectStomp = () => {
  if (stompClient) {
    stompClient.deactivate()
    stompClient = null
    connectionPromise = null
    console.log('WebSocket disconnected')
  }
}

export const subscribeToTopic = (topic, callback) => {
  return connectStomp().then(client => {
    return client.subscribe(topic, (message) => {
      try {
        const data = JSON.parse(message.body)
        callback(data)
      } catch (e) {
        console.error('Failed to parse message:', e)
      }
    })
  })
}