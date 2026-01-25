import { useState, useEffect, useRef } from 'react'

function App() {
  const [url, setUrl] = useState('https://books.toscrape.com/')
  const [projectId, setProjectId] = useState(null)
  const [wsStatus, setWsStatus] = useState('disconnected')
  const [fields, setFields] = useState([
    { name: 'product_title', type: 'Text', selector: '', icon: 'title', color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
    { name: 'current_price', type: 'Number', selector: '', icon: 'attach_money', color: 'text-blue-400', bg: 'bg-blue-400/10', active: true },
    { name: 'thumbnail_url', type: 'Image', selector: '', icon: 'image', color: 'text-purple-400', bg: 'bg-purple-400/10' },
  ])
  const [selection, setSelection] = useState(null)
  const [frame, setFrame] = useState(null)
  const [isConnecting, setIsConnecting] = useState(false)

  const ws = useRef(null)
  const reconnectInterval = useRef(null)

  const connectWS = () => {
    if (ws.current?.readyState === WebSocket.OPEN) return

    setIsConnecting(true)
    const socket = new WebSocket('ws://localhost:8000/ws/events')
    ws.current = socket

    socket.onopen = () => {
      setWsStatus('connected')
      setIsConnecting(false)
      clearInterval(reconnectInterval.current)
      reconnectInterval.current = null
    }

    socket.onclose = () => {
      setWsStatus('disconnected')
      setIsConnecting(false)
      if (!reconnectInterval.current) {
        reconnectInterval.current = setInterval(connectWS, 3000)
      }
    }

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'selection') {
          const payload = JSON.parse(data.selector)
          setSelection(payload)

          setFields(prev => prev.map(f => {
            if (f.active) {
              return { ...f, selector: payload.selector }
            }
            return f
          }))
        } else if (data.type === 'frame') {
          setFrame(`data:image/jpeg;base64,${data.data}`)
        }
      } catch (err) {
        // quiet fail
      }
    }
  }

  useEffect(() => {
    connectWS()
    return () => {
      if (reconnectInterval.current) clearInterval(reconnectInterval.current)
      if (ws.current) ws.current.close()
    }
  }, [])

  const startSession = async () => {
    try {
      const resp = await fetch(`http://localhost:8000/session/start?url=${encodeURIComponent(url)}`, {
        method: 'POST'
      })
      const data = await resp.json()
      setProjectId(data.project_id)
      console.log("Session started:", data.project_id)
    } catch (err) {
      console.error("Session start error:", err)
    }
  }

  const buildProject = async () => {
    if (!projectId) return
    try {
      const resp = await fetch(`http://localhost:8000/session/compile?project_id=${projectId}`, {
        method: 'POST'
      })
      const data = await resp.json()
      alert("Scraper build successful!")
    } catch (err) {
      console.error("Build error:", err)
    }
  }

  const handleRun = () => {
    setFrame(null)
    startSession()
  }

  const handleImageClick = (e) => {
    if (!ws.current || wsStatus !== 'connected' || !projectId) {
      if (!projectId) alert("Please click 'Run' to start a session first.")
      return
    }

    const rect = e.currentTarget.getBoundingClientRect()
    const x = Math.round(((e.clientX - rect.left) / rect.width) * 1280)
    const y = Math.round(((e.clientY - rect.top) / rect.height) * 720)

    ws.current.send(JSON.stringify({
      type: 'click',
      x: x,
      y: y,
      project_id: projectId
    }))
  }

  const toggleField = (name) => {
    setFields(prev => prev.map(f => ({ ...f, active: f.name === name })))
  }

  const addField = () => {
    const name = prompt("Field name:")
    if (!name) return
    const newField = {
      name: name.toLowerCase().replace(/\s+/g, '_'),
      type: 'Text',
      selector: '',
      icon: 'label',
      color: 'text-amber-400',
      bg: 'bg-amber-400/10',
      active: true
    }
    setFields(prev => prev.map(f => ({ ...f, active: false })).concat(newField))
  }

  const activeField = fields.find(f => f.active)

  return (
    <div className="bg-background-light dark:bg-background-dark text-white font-display h-screen flex flex-col overflow-hidden selection:bg-primary/30">
      {/* Header */}
      <header className="h-16 shrink-0 border-b border-border-dark flex items-center px-4 gap-4 bg-[#111722] z-20 shadow-lg">
        <div className="flex items-center gap-2 mr-2">
          <div className="size-8 bg-gradient-to-br from-primary to-purple-600 rounded-lg flex items-center justify-center">
            <span className="material-symbols-outlined text-white text-xl">smart_toy</span>
          </div>
          <span className="font-bold text-lg tracking-tight hidden md:block">ScrapeWizard Studio</span>
        </div>

        <div className="flex-1 max-w-3xl flex items-center">
          <div className="flex w-full items-stretch rounded-lg shadow-sm">
            <div className={`flex items-center justify-center pl-3 border border-r-0 border-border-dark bg-surface-dark rounded-l-lg ${wsStatus === 'connected' ? 'text-green-500' : 'text-text-muted'}`}>
              <span className="material-symbols-outlined text-sm">
                {wsStatus === 'connected' ? 'link' : 'link_off'}
              </span>
            </div>
            <input
              className="form-input flex w-full min-w-0 flex-1 resize-none overflow-hidden text-white focus:outline-0 focus:ring-0 border border-border-dark bg-surface-dark focus:border-primary h-10 placeholder:text-text-muted px-3 text-sm font-normal font-mono"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleRun()}
            />
            <div
              onClick={handleRun}
              className="text-text-muted flex border border-l-0 border-border-dark bg-surface-dark items-center justify-center px-3 rounded-r-lg hover:text-white cursor-pointer transition-colors"
            >
              <span className="material-symbols-outlined text-lg">refresh</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 ml-auto">
          <button
            onClick={buildProject}
            className="flex items-center justify-center rounded-lg h-9 px-3 border border-border-dark text-text-muted hover:text-white hover:bg-surface-dark text-sm font-medium transition-colors disabled:opacity-50"
            disabled={!projectId}
          >
            <span className="material-symbols-outlined text-lg mr-1.5">build</span>
            Build
          </button>
          <button
            onClick={handleRun}
            className="flex items-center justify-center rounded-lg h-9 px-4 bg-primary hover:bg-blue-600 text-white text-sm font-bold shadow-lg shadow-blue-900/20 transition-all"
          >
            <span className="material-symbols-outlined text-lg mr-1.5">play_arrow</span>
            Run
          </button>
        </div>
      </header>

      <main className="flex-1 flex overflow-hidden">
        {/* Schema aside */}
        <aside className="w-64 border-r border-border-dark bg-[#111722] flex flex-col shrink-0">
          <div className="p-3 border-b border-border-dark flex justify-between items-center">
            <h3 className="text-white text-sm font-bold tracking-tight">Schema</h3>
            <button
              onClick={addField}
              className="text-text-muted hover:text-white p-1 rounded hover:bg-white/5 transition-colors"
            >
              <span className="material-symbols-outlined text-lg">add</span>
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {fields.map((field) => (
              <div
                key={field.name}
                onClick={() => toggleField(field.name)}
                className={`group flex items-center gap-3 hover:bg-surface-dark border border-transparent hover:border-border-dark rounded-lg p-2 cursor-pointer transition-all ${field.active ? 'ring-1 ring-primary/50 bg-surface-dark' : 'bg-surface-dark/50'}`}
              >
                <div className={`${field.color} ${field.bg} rounded p-1.5 shrink-0`}>
                  <span className="material-symbols-outlined text-lg">{field.icon}</span>
                </div>
                <div className="flex flex-col min-w-0 flex-1">
                  <p className="text-white text-xs font-bold truncate">{field.name}</p>
                  <p className="text-text-muted text-[10px] truncate font-mono">{field.selector || 'Click to select'}</p>
                </div>
              </div>
            ))}
          </div>
        </aside>

        {/* Center: Live View */}
        <div className="flex-1 flex flex-col min-w-0 bg-[#0c1017]">
          <div className="h-8 bg-[#192233] border-b border-border-dark flex items-center px-4 text-xs text-text-muted justify-between shrink-0">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${wsStatus === 'connected' ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></span>
              <span className="ml-1 uppercase tracking-widest font-bold text-[9px]">{wsStatus}</span>
            </div>
            {projectId && <div className="text-[10px] font-mono text-primary">SESSION: {projectId}</div>}
          </div>

          <div className="flex-1 overflow-auto relative bg-[#0c1017] flex items-start justify-center p-4">
            <div className="relative w-full max-w-[1280px] bg-black shadow-2xl rounded-lg overflow-hidden border border-white/5 group">
              {frame ? (
                <img
                  src={frame}
                  onClick={handleImageClick}
                  className="w-full h-auto cursor-crosshair select-none"
                  alt="Live Browser"
                  draggable={false}
                />
              ) : (
                <div className="aspect-video w-full flex flex-col items-center justify-center p-12 text-center bg-[#111722]">
                  {isConnecting && wsStatus !== 'connected' ? (
                    <div className="flex flex-col items-center">
                      <div className="size-12 border-4 border-primary border-t-transparent rounded-full animate-spin mb-4"></div>
                      <p className="text-text-muted text-sm font-medium">Reconnecting to Backend...</p>
                    </div>
                  ) : (
                    <div className="max-w-md">
                      <span className="material-symbols-outlined text-5xl text-primary/30 mb-4">captive_portal</span>
                      <h2 className="text-xl font-bold mb-2">Browser Interface Disconnected</h2>
                      <p className="text-text-muted text-sm mb-6">Enter a target URL and hit "Run" to initialize the selection environment.</p>
                      <button onClick={handleRun} className="px-6 py-2 bg-primary rounded-lg font-bold text-sm hover:scale-105 transition-transform">Start Session</button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Bottom Panel */}
          <div className="h-64 border-t border-border-dark bg-[#111722] flex flex-col shrink-0">
            <div className="flex items-center px-4 border-b border-border-dark bg-surface-dark shrink-0">
              <button className="px-4 py-2 text-xs font-bold text-white border-b-2 border-primary bg-[#192233]">Visual Inspector</button>
              <button className="px-4 py-2 text-xs font-medium text-text-muted hover:text-white">Live Data</button>
            </div>
            <div className="flex-1 overflow-auto p-4 font-mono text-[11px]">
              {selection ? (
                <div className="space-y-4">
                  <div className="p-3 bg-black/40 rounded border border-white/5">
                    <p className="text-primary font-bold mb-2 uppercase text-[9px] tracking-widest">Active Section</p>
                    <pre className="text-purple-300 whitespace-pre-wrap">{selection.selector}</pre>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 bg-black/20 rounded">
                      <p className="text-text-muted text-[9px] mb-1">Tag</p>
                      <p className="text-white">{selection.tag}</p>
                    </div>
                    <div className="p-3 bg-black/20 rounded">
                      <p className="text-text-muted text-[9px] mb-1">Matches</p>
                      <p className="text-emerald-400 font-bold">{selection.matchCount || 0} elements</p>
                    </div>
                  </div>
                  {selection.samples && selection.samples.length > 0 && (
                    <div className="p-3 bg-black/20 rounded border border-white/5">
                      <p className="text-text-muted text-[9px] mb-2 uppercase tracking-widest">Live Samples</p>
                      <div className="space-y-1">
                        {selection.samples.map((s, i) => (
                          <div key={i} className="flex gap-2 items-center text-[10px] text-white/70">
                            <span className="size-1.5 rounded-full bg-emerald-500/50"></span>
                            <span className="truncate">{s}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="h-full flex items-center justify-center text-text-muted opacity-50">
                  Waiting for element selection...
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Info */}
        <aside className="w-80 border-l border-border-dark bg-[#111722] flex flex-col shrink-0 overflow-y-auto">
          <div className="p-4 border-b border-border-dark">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-white text-sm font-bold tracking-tight uppercase text-[10px] tracking-widest opacity-50">Global Stats</h3>
              <span className="bg-primary/10 text-primary text-[10px] px-2 py-0.5 rounded-full font-bold border border-primary/20">AGENT READY</span>
            </div>
            <div className="space-y-4">
              <div className="p-3 bg-surface-dark/50 rounded-lg border border-border-dark">
                <p className="text-[10px] text-text-muted mb-2 font-bold uppercase tracking-tighter">Confidence Score</p>
                <div className="flex items-center gap-3">
                  <div className="flex-1 h-1.5 bg-background-dark rounded-full overflow-hidden">
                    <div className="h-full bg-emerald-500 w-[94%]" style={{ boxShadow: '0 0 10px rgba(16, 185, 129, 0.4)' }}></div>
                  </div>
                  <span className="text-xs font-bold text-emerald-400">94%</span>
                </div>
              </div>
            </div>
          </div>
          <div className="p-4">
            <h4 className="text-[10px] font-bold text-text-muted mb-3 uppercase tracking-widest">Self-Healing Log</h4>
            <div className="space-y-2">
              {[
                { t: '12:44:01', m: 'Bridge injected successfully', s: 'done' },
                { t: '12:44:05', m: 'Detected Chromium session', s: 'check' },
                { t: '12:45:10', m: 'Pattern miner optimized', s: 'bolt' },
              ].map((log, i) => (
                <div key={i} className="flex gap-3 text-[10px]">
                  <span className="text-text-muted font-mono">{log.t}</span>
                  <span className="text-white/80">{log.m}</span>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </main>
    </div>
  )
}

export default App
