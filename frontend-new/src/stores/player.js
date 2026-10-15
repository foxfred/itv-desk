import { defineStore } from 'pinia'
import { ref } from 'vue'

export const usePlayerStore = defineStore('player', () => {
      const state = ref('hidden')     // 'hidden' | 'drawer' | 'pip' | 'full'
  const width = ref(480)          

    const currentChannel = ref(null) 
  const channelList = ref([])      
  const channelIndex = ref(-1)     
  const currentUrl = ref('')       
  const currentUrlNote = ref('')   
    const videoInfo = ref({ w: 0, h: 0, fps: 0, engine: '' })

    function open(channel, list = null, idx = -1) {
    if (!channel || !channel.url) return
    const sameChannel = channel.url === currentUrl.value
    currentChannel.value = channel
    currentUrl.value = channel.url
    currentUrlNote.value = channel.url_note || ''
    if (list && Array.isArray(list) && list.length > 0) {
      channelList.value = list
      channelIndex.value = idx >= 0 ? idx : list.findIndex(ch => ch.url === channel.url)
    }
        if (state.value === 'hidden') state.value = 'drawer'
    return { sameChannel, changed: !sameChannel }
  }

  function next() {
    if (channelIndex.value < 0 || !channelList.value.length) return null
    if (channelIndex.value >= channelList.value.length - 1) return null
    channelIndex.value++
    const ch = channelList.value[channelIndex.value]
    if (ch && ch.url) {
      open(ch, channelList.value, channelIndex.value)
      return ch
    }
    return null
  }

  function prev() {
    if (channelIndex.value <= 0 || !channelList.value.length) return null
    channelIndex.value--
    const ch = channelList.value[channelIndex.value]
    if (ch && ch.url) {
      open(ch, channelList.value, channelIndex.value)
      return ch
    }
    return null
  }

  function setState(s) {
    if (['hidden', 'drawer', 'pip', 'full'].includes(s)) state.value = s
  }

  function exitPip() {
    if (state.value === 'pip') state.value = 'drawer'
  }

  function close() {
    state.value = 'hidden'
        currentChannel.value = null
    currentUrl.value = ''
    currentUrlNote.value = ''
  }

  return {
    // state
    state, width,
    currentChannel, channelList, channelIndex,
    currentUrl, currentUrlNote,
    videoInfo,
    // actions
    open, next, prev, setState, exitPip, close,
  }
})
