// 实时推送客户端（SSE / Server-Sent Events）
// 对应后端 /api/logs/stream 与 /api/events/stream。
// 设计原则：优先使用 EventSource 实时接收；不支持或连接失败时通过 onError 回调
// 回退到既有的轮询接口（/api/logs、/api/stats、/check/status、/scrape/status），
// 因此即使 SSE 不可用，原有轮询路径依旧可用，不会产生破坏性变更。

function _openStream(url) {
  if (typeof EventSource === 'undefined') return null
  try {
    return new EventSource(url)
  } catch (e) {
    return null
  }
}

/**
 * 订阅实时日志流。
 * @param {object} opts
 * @param {(msg:string)=>void} opts.onMessage 收到一条新日志
 * @param {()=>void} [opts.onOpen] 连接建立
 * @param {(err:Error)=>void} [opts.onError] 出错/断开（用于回退轮询）
 * @returns {EventSource|null}
 */
export function subscribeLogsSSE({ onMessage, onOpen, onError } = {}) {
  const es = _openStream('/api/logs/stream')
  if (!es) {
    onError && onError(new Error('EventSource 不可用'))
    return null
  }
  es.onopen = () => onOpen && onOpen()
  es.onmessage = (ev) => {
    try {
      const obj = JSON.parse(ev.data)
      if (obj && obj.msg != null) onMessage && onMessage(obj.msg)
    } catch (e) {
      /* 忽略非法帧 */
    }
  }
  es.onerror = () => onError && onError(new Error('logs 流断开'))
  return es
}

/**
 * 订阅运行快照流（stats / check / scrape 等命名事件）。
 * @param {object} opts
 * @param {(obj:{name:string,data:any,t:number})=>void} opts.onEvent
 * @param {()=>void} [opts.onOpen]
 * @param {(err:Error)=>void} [opts.onError]
 * @returns {EventSource|null}
 */
export function subscribeEventsSSE({ onEvent, onOpen, onError } = {}) {
  const es = _openStream('/api/events/stream')
  if (!es) {
    onError && onError(new Error('EventSource 不可用'))
    return null
  }
  es.onopen = () => onOpen && onOpen()
  es.onmessage = (ev) => {
    try {
      const obj = JSON.parse(ev.data)
      if (obj && obj.name) onEvent && onEvent(obj)
    } catch (e) {
      /* 忽略非法帧 */
    }
  }
  es.onerror = () => onError && onError(new Error('events 流断开'))
  return es
}
