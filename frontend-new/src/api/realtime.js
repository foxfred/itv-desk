
function _openStream(url) {
  if (typeof EventSource === 'undefined') return null
  try {
    return new EventSource(url)
  } catch (e) {
    return null
  }
}

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
          }
  }
  es.onerror = () => onError && onError(new Error('logs 流断开'))
  return es
}

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
          }
  }
  es.onerror = () => onError && onError(new Error('events 流断开'))
  return es
}
