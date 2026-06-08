/**
 * STOMP WebSocket 客户端封装。
 *
 * 任务进度等实时推送经网关 /ws/stomp 订阅；连接为进程级单例，避免详情页反复打开时重复握手。
 */
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

    // 已连接则直接复用，减少任务详情页切换时的重复订阅开销。
    if (stompClient && stompClient.connected) {
      resolve(stompClient)
      return
    }

    // 并发 connect 调用共享同一 Promise，避免短时间多次 activate 造成重复连接。
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
      // 10 秒未连上则失败，上层 useTaskMonitor 会降级为纯轮询。
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

/**
 * 订阅 STOMP topic 并解析 JSON 消息体。
 * @returns {Promise<{ unsubscribe: Function }>} 订阅句柄，组件卸载时需调用 unsubscribe。
 */
export const subscribeToTopic = (topic, callback) => {
  return connectStomp().then(client => {
    return client.subscribe(topic, (message) => {
      try {
        const data = JSON.parse(message.body)
        callback(data)
      } catch (e) {
        // 非 JSON 或协议变更时不抛错，避免打断轮询兜底链路。
        console.error('Failed to parse message:', e)
      }
    })
  })
}