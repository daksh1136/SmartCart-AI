import { useEffect, useRef, useState } from 'react'
import { BrowserMultiFormatReader } from '@zxing/browser'
import JsBarcode from 'jsbarcode'
import {
  Activity, ArrowDown, ArrowRight, BadgeCheck, Barcode, Camera,
  CheckCircle2, ChevronRight, CircleAlert, CreditCard, Eye, FileCheck2,
  Info, Minus, Package, Plus, RefreshCw, ScanLine, ShieldCheck, Scale, Layers3,
  ShoppingBasket, Smartphone, Sparkles, VideoOff, X, DoorOpen
} from 'lucide-react'

async function fetchWithOperatorKey(url, options) {
  const savedKey = sessionStorage.getItem('smartcart-operator-key')
  if (savedKey) options.headers = { ...options.headers, 'X-SmartCart-Operator-Key': savedKey }
  let response
  try { response = await fetch(url, options) }
  catch { throw new Error('Cannot connect to FastAPI. Start the backend on port 8000.') }
  if (response.status === 401 && options.method !== 'GET') {
    const key = window.prompt('Enter the demo operator key to use the shared shopping session')
    if (!key) throw new Error('Action cancelled: operator key is required')
    sessionStorage.setItem('smartcart-operator-key', key)
    options.headers['X-SmartCart-Operator-Key'] = key
    response = await fetch(url, options)
  }
  return response
}

async function api(path, method = 'GET', payload) {
  const options = { method, headers: {} }
  if (payload !== undefined) {
    options.headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(payload)
  }
  const response = await fetchWithOperatorKey(`/api${path}`, options)
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Request failed')
  return body
}

const money = (paise) => `₹${(paise / 100).toLocaleString('en-IN', {maximumFractionDigits: 2, minimumFractionDigits: 0})}`
const classNameFor = (s) => ({MATCHED:'success', CLEAR:'muted', UNSCANNED:'warning', OVER_SCANNED:'warning'}[s] || 'muted')
const labelFor = (s) => ({MATCHED:'Verified', CLEAR:'Clear', UNSCANNED:'Missing scan', OVER_SCANNED:'Extra scan'}[s] || s)

function BarcodeLabel({ product }) {
  const ref = useRef(null)
  useEffect(() => {
    if (ref.current) JsBarcode(ref.current, product.barcode, {format:'EAN13', width:1.4, height:42, fontSize:13, margin:4})
  }, [product.barcode])
  return <div className="barcode-card"><span>{product.emoji} {product.name}</span>{product.demo_barcode&&<small>Demo-only code · not a retail barcode</small>}<svg ref={ref}/></div>
}

function Scanner({ onScan, onClose }) {
  const video = useRef(null)
  const controls = useRef(null)
  const busy = useRef(false)
  const [error, setError] = useState('')
  useEffect(() => {
    let disposed = false
    const reader = new BrowserMultiFormatReader()
    ;(async () => {
      try {
        if (!navigator.mediaDevices) throw new Error('Camera scanning needs HTTPS on phones (or localhost on this laptop). Use manual barcode entry meanwhile.')
        const ctrl = await reader.decodeFromConstraints({video: {facingMode: {ideal:'environment'}}}, video.current, (result, _err, scanControls) => {
          if (result && !busy.current) {
            busy.current = true
            scanControls.stop()
            onScan(result.getText())
            onClose()
          }
        })
        if (disposed) ctrl.stop(); else controls.current = ctrl
      } catch(e) { if (!disposed) setError(e.message || 'Cannot access camera') }
    })()
    return () => {disposed = true; controls.current?.stop()}
  }, []) // single scan per dialog; closes on success
  return <div className="modal-backdrop" onClick={onClose}>
    <div className="scanner-modal" onClick={e=>e.stopPropagation()}>
      <div className="modal-title"><div><div className="eyebrow">MOBILE SCANNER</div><h3>Scan product barcode</h3></div><button className="icon-btn" onClick={onClose}><X size={20}/></button></div>
      <div className="scan-video"><video ref={video} muted playsInline autoPlay/><span className="scan-outline"/><div className="scan-caption">Position the printed product barcode inside the frame</div></div>
      {error && <p className="alertline">{error}</p>}
      <p className="muted small">Scan one of the printed demo barcodes. Prototype product codes work only in this app and are not retail SKUs.</p>
    </div>
  </div>
}

function CameraPanel({ refresh, notify, products, sku }) {
  const video = useRef(null)
  const stream = useRef(null)
  const timer = useRef(null)
  const pending = useRef(false)
  const [running, setRunning] = useState(false)
  const [vision, setVision] = useState(null)
  const [msg, setMsg] = useState('')
  const [aiEnabled,setAiEnabled] = useState(false)
  const [aiResult,setAiResult] = useState(null)
  const [aiError,setAiError] = useState('')
  const aiTimer = useRef(null)
  const aiBusy = useRef(false)
  const [skuResult, setSkuResult] = useState(null)
  const [skuError, setSkuError] = useState('')
  const [skuBusy, setSkuBusy] = useState(false)
  const skuRegistered = sku?.enrolled || []
  const skuRequest = async (path, actionText) => {
    if (skuBusy || !running) return
    setSkuBusy(true)
    setSkuError('')
    try {
      const response = await fetchWithOperatorKey(`/api/vision/sku/${path}`, {
        method:'POST', headers:{'Content-Type':'image/jpeg'}, body:await shot()
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(result.detail || 'Appearance check failed')
      if (path === 'recognize') setSkuResult(result)
      else {setSkuResult(null);notify(actionText);await refresh()}
    } catch(e) {setSkuError(e.message || 'Appearance check failed')}
    finally {setSkuBusy(false)}
  }
  const stop = () => {
    clearInterval(timer.current)
    clearInterval(aiTimer.current)
    aiTimer.current = null
    setAiEnabled(false)
    setAiResult(null)
    timer.current = null
    stream.current?.getTracks().forEach(t=>t.stop())
    stream.current = null
    if (video.current) video.current.srcObject = null
    setRunning(false)
  }
  useEffect(() => () => {
    clearInterval(timer.current)
    clearInterval(aiTimer.current)
    stream.current?.getTracks().forEach(t=>t.stop())
  }, [])
  const shot = () => new Promise((resolve, reject) => {
    if (!video.current?.videoWidth) return reject(new Error('Camera is still warming up'))
    const canvas = document.createElement('canvas')
    canvas.width = 640; canvas.height = 360
    canvas.getContext('2d').drawImage(video.current, 0, 0, 640, 360)
    canvas.toBlob(b=>b ? resolve(b) : reject(new Error('Snapshot failed')), 'image/jpeg', 0.76)
  })
  const send = async (endpoint, blob) => {
    const res = await fetchWithOperatorKey(`/api/vision/${endpoint}`, {method:'POST', headers:{'Content-Type':'image/jpeg'}, body:blob})
    const json = await res.json()
    if (!res.ok) throw new Error(json.detail || 'Vision request failed')
    setVision(json)
    if (json.rejected?.length) setMsg(`Camera saw a change but cart update was rejected: ${json.rejected.map(x=>x.reason).join('; ')}. Check the session or reset with the shelf restocked.`)
    if (json.transitions?.length) {refresh(); notify(`${json.transitions.map(x=>`${x.zone}: ${x.action}`).join(', ')} detected by camera`)}
    return json
  }
  const tick = async () => {
    if (pending.current || !video.current?.videoWidth) return
    pending.current = true
    try { await send('frame', await shot()) }
    catch (e) {setMsg(e.message)}
    finally {pending.current = false}
  }
  const aiTick = async () => {
    if (aiBusy.current || !video.current?.videoWidth) return
    aiBusy.current = true
    try {
      const response = await fetchWithOperatorKey('/api/vision/ai/frame', {
        method:'POST', headers:{'Content-Type':'image/jpeg'}, body:await shot()
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(result.detail || 'AI tracking error')
      setAiResult(result)
      setAiError('')
    } catch(e) { setAiError(e.message || 'AI tracking error'); setAiEnabled(false) }
    finally { aiBusy.current = false }
  }
  useEffect(() => {
    if (!running || !aiEnabled) return undefined
    aiTick()
    aiTimer.current = setInterval(aiTick,2800)
    return () => {clearInterval(aiTimer.current); aiTimer.current=null}
  },[running,aiEnabled])
  const start = async () => {
    try {
      setMsg('')
      const s = await navigator.mediaDevices.getUserMedia({video:{width:{ideal:1280},height:{ideal:720}},audio:false})
      stream.current = s
      video.current.srcObject = s
      await video.current.play()
      setRunning(true)
      timer.current = setInterval(tick, 550)
      notify('Camera running. Calibrate with all shelf zones empty first.')
    } catch(e) {setMsg(e.message || 'Camera permission denied'); stop()}
  }
  const calibrate = async kind => {
    try {
      setMsg('')
      const result = await send(`calibrate/${kind}`, await shot())
      notify(kind === 'empty' ? 'Empty shelf reference captured' : 'Stocked shelf reference captured')
      if (result.calibration_warning?.length) setMsg('Poor image contrast in zones: ' + result.calibration_warning.join(', ') + '. Reposition products, then recalibrate.')
    } catch(e) {setMsg(e.message)}
  }
  const zones = vision?.zones ?? {A:'UNKNOWN', B:'UNKNOWN', C:'UNKNOWN'}
  return <div className="panel camera-panel">
    <div className="row between wrap"><div><div className="eyebrow">COMPUTER VISION · FIXED-ZONE MODE</div><h3>Live shelf monitoring</h3></div><span className={`pill ${running ? 'success':'muted'}`}><span className="status-dot"/> {running?'Camera live':'Camera off'}</span></div>
    <div className="camera-window">
      <video ref={video} autoPlay muted playsInline className={!running?'hidden-video':''}/>
      {!running && <div className="camera-empty"><Camera size={40}/><strong>Camera is offline</strong><span>Start your laptop camera to monitor 3 shelf zones.</span></div>}
      {running && <div className="zone-grid">{'ABC'.split('').map(z=><div className="zone-marker" key={z}><span>ZONE {z}</span><small>{zones[z] || 'UNKNOWN'}</small></div>)}</div>}
      {running && aiEnabled && aiResult?.detections?.map((d,index)=>{
        const [x1,y1,x2,y2]=d.box
        const w=aiResult.frame_width||640, h=aiResult.frame_height||360
        return <div className="ai-box" key={`${d.track_id ?? 'untracked'}-${index}`} style={{left:`${x1/w*100}%`,top:`${y1/h*100}%`,width:`${(x2-x1)/w*100}%`,height:`${(y2-y1)/h*100}%`}}><span>{d.label} {Math.round(d.confidence*100)}%{d.track_id!==null?` · #${d.track_id}`:''}</span></div>
      })}
    </div>
    <div className="camera-actions">
      <button className={`btn ${running ? 'secondary':'primary'}`} onClick={running ? stop : start}>{running?<VideoOff size={17}/>:<Camera size={17}/>} {running?'Stop camera':'Start camera'}</button>
      <button className="btn secondary" onClick={()=>calibrate('empty')} disabled={!running}>1. Capture empty</button>
      <button className="btn secondary" onClick={()=>calibrate('full')} disabled={!running}>2. Capture stocked</button>
    </div>
    <p className="muted small">Keep the webcam fixed. First remove all 3 products and click <b>Capture empty</b>. Then place one product in each zone and click <b>Capture stocked</b>. Keep hands out of both reference images. A pickup is confirmed after several consistent frames.</p>
    <div className="phase7-camera-diagnostics" aria-live="polite">
      <strong>Camera health</strong>
      <span>{!vision?.has_empty ? 'Needs empty reference' : !vision?.has_full ? 'Needs stocked reference' : vision.calibration_warning?.length ? `Weak zones: ${vision.calibration_warning.join(', ')}` : vision.stream_recent ? 'Receiving frames' : 'Calibrated, waiting for frames'}</span>
      <small>{vision?.frames_processed ?? 0} server-processed frames · {vision?.last_frame_at ? `Last frame ${new Date(vision.last_frame_at).toLocaleTimeString()}` : 'No frame received yet'}</small>
      {vision?.rejected_events?.length > 0 && <small className="camera-reject">{vision.rejected_events.length} recent camera event(s) rejected. Check the demo session state.</small>}
      <small>Camera health measures stream/calibration state, not retail recognition accuracy.</small>
    </div>
    <details className="advanced-vision">
      <summary>Experimental vision tools <span>Advisory only · never changes cart counts</span></summary>
      <div className="ai-panel">
      <div><strong>Phase 4 · YOLO + ByteTrack overlay (experimental)</strong><p>Recognizes generic object classes and track IDs, not exact shampoo/biscuit/cola SKUs. This overlay never updates the physical cart; fixed-zone monitoring and sensor fusion remain authoritative.</p></div>
      <button className={`btn ${aiEnabled?'primary':'secondary'}`} disabled={!running} onClick={()=>{setAiError('');setAiResult(null);setAiEnabled(v=>!v)}}>{aiEnabled?'Stop AI overlay':'Enable AI overlay'}</button>
      {aiResult && <div className="ai-stats">{aiResult.detections.length} objects · {aiResult.detections.filter(d=>d.track_id!==null).length} tracked · Frame {aiResult.frame_count}</div>}
      {aiError && <div className="note danger"><CircleAlert size={16}/>{aiError}</div>}
      <p className="muted small">Install optional AI requirements separately before enabling. First inference may download free weights. Expect slower CPU inference.</p>
    </div>
      <div className="sku-panel">
      <div><div className="eyebrow">PHASE 5 · EXAMPLE-BASED SKU APPEARANCE</div>
        <h3>Teach your three products</h3>
        <p className="muted small">Keep the webcam fixed and place <b>Shampoo in A</b>, <b>Biscuits in B</b>, and <b>Cola in C</b>. Capture each labeled sample while all products are still and fully visible. Use the same actual packages during the demo. This is a lightweight visual similarity check, <b>not trained retail SKU recognition</b>.</p>
      </div>
      <div className="sku-enroll-grid">{products.filter(p=>['A','B','C'].includes(p.zone)).map(p=><button key={p.id} className="btn secondary sku-enroll-btn" disabled={!running||skuBusy} onClick={()=>skuRequest(`enroll/${p.id}`,`${p.name} example saved`)}>
        <Camera size={15}/>{skuRegistered.includes(p.id)?'✓ Re-teach':'Teach'} {p.name} · {p.zone}
      </button>)}</div>
      <div className="sku-actions">
        <span className={`pill ${sku?.ready?'success':'muted'}`}>{skuRegistered.length}/3 example images saved</span>
        <button className="btn primary" disabled={!running||skuBusy||!sku?.ready} onClick={()=>skuRequest('recognize','Visual check complete')}><Eye size={16}/>{skuBusy?'Checking…':'Check product appearances'}</button>
      </div>
      {skuResult && <>
        <p className="muted small">Latest webcam snapshot: {new Date(skuResult.created_at).toLocaleTimeString()}. Results are advisory and do not change or verify the cart.</p>
        <div className="sku-result-grid">{skuResult.zones.map(z=><div className="sku-result" key={z.zone}>
          <div><strong>Zone {z.zone}</strong><span className={`pill tiny ${z.result==='MATCH'?'success':z.result==='POSSIBLE_MISMATCH'?'warning':'muted'}`}>{z.result.replace('_',' ')}</span></div>
          <span>Expected: {z.expected}</span>
          <span>{z.result==='EMPTY'?'Shelf zone appears empty':z.predicted?`Looks like: ${z.predicted}`:'Appearance inconclusive'}</span>
          {z.confidence!==null&&<small>Visual similarity: {Math.round(z.confidence*100)}% (not calibrated probability)</small>}
        </div>)}</div>
      </>}
      {skuError && <div className="note danger"><CircleAlert size={16}/>{skuError}</div>}
      <p className="muted small">If lighting, orientation or products change, re-teach the images. A possible mismatch needs human verification. Visual matches never authorize billing.</p>
      </div>
    </details>
    {vision?.ready && <div className="note good"><CheckCircle2 size={16}/> Shelf zones calibrated. Remove one product to test detection.</div>}
    {!!msg && <div className="note danger"><CircleAlert size={16}/>{msg}</div>}
  </div>
}

function FusionPanel({ data, action, busy }) {
  const fusion = data?.fusion || {}
  const products = (data?.products || []).filter(p=>fusion.expected_weights?.[p.id] !== undefined)
  const pending = fusion.pending || []
  const enabled = !!fusion.enabled
  return <div className="panel fusion-panel">
    <div className="panel-head"><div><div className="eyebrow">PHASE 3 · SENSOR FUSION</div><h2>Camera + simulated shelf weight</h2></div>
      <button className={`btn ${enabled?'primary':'secondary'}`} disabled={busy} onClick={()=>action('/fusion/mode', {enabled:!enabled},enabled?'Camera-only mode':'Sensor fusion enabled')}>
        <Layers3 size={17}/> {enabled?'Fusion ON · switch off':'Enable 2-signal mode'}
      </button>
    </div>
    <p className="muted small">In fusion mode, a shelf pickup is counted <b>only when camera and weight agree</b> on the product and action. Weight readings are simulated here; no physical sensor is required. You can either use the real calibrated webcam or the test-camera buttons below.</p>
    {enabled ? <>
      <div className="fusion-summary">
        <span className={`pill ${fusion.blocked?'warning':'success'}`}>{fusion.blocked?`${fusion.pending_count} unmatched signal(s) · checkout paused`:'No outstanding evidence'}</span>
        <button className="btn secondary" disabled={busy || !pending.length} onClick={()=>{
          if (window.confirm('Discard unmatched fusion events? This does not change the physical cart.')) action('/fusion/clear',undefined,'Unmatched evidence cleared')
        }}>Clear pending evidence</button>
      </div>
      <div className="fusion-grid">
        {products.map(p=>{
          const grams = fusion.weights?.[p.id] ?? 0
          const expected = fusion.expected_weights?.[p.id] ?? 1
          const signals = pending.filter(e=>e.product_id===p.id)
          return <div className="fusion-tile" key={p.id}>
            <div className="fusion-product"><span className="product-emoji">{p.emoji}</span><div><strong>{p.name}</strong><small>Zone {p.zone} · expected {expected} g</small></div></div>
            <div className="weight-number"><Scale size={16}/><strong>{grams} g</strong><span>{fusion.weight_states?.[p.id]||'UNKNOWN'}</span></div>
            <div className="weight-meter"><div style={{width:`${Math.min(100,Math.max(0,grams/expected*100))}%`}}/></div>
            <div className="fusion-buttons"><label>1. Camera observation (use these OR live camera)</label>
              <div><button className="btn small-btn secondary" disabled={busy} onClick={()=>action('/fusion/camera',{product_id:p.id,action:'pickup'},`Camera pickup: ${p.name}`)}>Camera pickup</button><button className="btn small-btn secondary" disabled={busy} onClick={()=>action('/fusion/camera',{product_id:p.id,action:'return'},`Camera return: ${p.name}`)}>Camera return</button></div>
            </div>
            <div className="fusion-buttons"><label>2. Simulated weight sensor</label>
              <div><button className="btn small-btn primary" disabled={busy || grams === 0} onClick={()=>action('/fusion/weight',{product_id:p.id,weight_grams:0},`${p.name} weight dropped to 0g`)}>Remove weight</button><button className="btn small-btn secondary" disabled={busy || grams === expected} onClick={()=>action('/fusion/weight',{product_id:p.id,weight_grams:expected},`${p.name} weight restored`)}>Restock weight</button></div>
            </div>
            <div className="fusion-evidence">{signals.length ? signals.map(e=><div key={e.id} className="evidence-line"><CircleAlert size={14}/>{e.source.toUpperCase()} · {e.action.toUpperCase()} · {e.state==='REVIEW_REQUIRED'?'Needs review':'Waiting for match'}</div>) : <span>✓ No pending observations for this shelf.</span>}</div>
          </div>
        })}
      </div>
      <div className="tip"><Info size={17}/><span>Demo: <b>Camera pickup → Remove weight → Scan product → Verified</b>. In reverse, use <b>Camera return → Restock weight → Remove scan</b>. Pending or uncertain evidence blocks checkout.</span></div>
    </> : <div className="note good"><CheckCircle2 size={16}/> Camera-only and manual pickup simulation continue to work normally. Enable sensor fusion to require a matching second signal.</div>}
  </div>
}

function DemoGuide({ data, tab, setTab, action, busy }) {
  const demo = data?.demo
  const steps = demo?.steps || []
  const completed = steps.filter(s=>s.done).length
  return <section className="panel phase7-guide" aria-label="Guided hackathon demonstration">
    <div className="panel-head"><div><div className="eyebrow">PHASE 7 · LIVE PRESENTATION</div><h2>Five-step judge walkthrough</h2></div><span className="pill muted">{completed}/{steps.length || 5} complete</span></div>
    <p className="muted small">Real recorded actions, not fabricated results. Start with the three products stocked. Show how an unscanned pickup blocks the simulated exit, then scan the item and complete mock billing.</p>
    <div className="phase7-steps">{steps.map((step, index)=>
      <div key={step.title} className={`phase7-step ${step.done?'done':demo?.current_step===index?'current':''}`}>
        <span className="phase7-step-number">{step.done?<CheckCircle2 size={16}/>:index+1}</span>
        <div><strong>{step.title}</strong><small>{step.help}</small></div>
      </div>
    )}</div>
    <div className="phase7-guide-foot">
      <span><Info size={15}/> {demo?.sensor_type==='SIMULATED_WEIGHT'?'Fusion enabled: shelf weight data is SIMULATED.':'Camera-only or manual pickup demo. No real shelf sensors.'}</span>
      <div>
        <button className="btn secondary" disabled={busy} onClick={()=>{if(window.confirm('Reset all cart data and receipt? If using camera, restock all zones first.')) action('/reset',undefined,'Demo session reset')}}><RefreshCw size={15}/> Reset demo</button>
        <button className="btn secondary" onClick={()=>setTab(tab==='shopper'?'operations':'shopper')}><ArrowRight size={15}/> {tab==='shopper'?'Shelf operations':'Shopper app'}</button>
      </div>
    </div>
  </section>
}

function App() {
  const [tab, setTab] = useState('shopper')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [manual, setManual] = useState('')
  const [scanner, setScanner] = useState(false)
  const [busy, setBusy] = useState(false)
  const [showLabels, setShowLabels] = useState(false)
  const [exitOutcome, setExitOutcome] = useState(null)
  const notify = (msg) => {setNotice(msg); setTimeout(()=>setNotice(''), 3900)}
  const refresh = async () => {
    try { const d = await api('/status'); setData(d); setError('') }
    catch(e) {setError(e.message)}
  }
  useEffect(()=>{refresh();const timer=setInterval(refresh,1300);return ()=>clearInterval(timer)},[])
  const action = async (path, body, message='Updated') => {
    if (busy) return
    setBusy(true)
    try {const d = await api(path, 'POST', body); if (path !== '/checkout') setData(d); if (path === '/reset') setExitOutcome(null); await refresh();notify(message)}
    catch(e){setError(e.message);notify(e.message)}
    finally {setBusy(false)}
  }
  const exitAttempt = async () => {
    if (busy) return
    setBusy(true)
    setExitOutcome(null)
    try {
      const receipt = await api('/exit/attempt', 'POST')
      setExitOutcome({approved:true, message:`Exit approved — ${receipt.id} · ${money(receipt.total_paise)} (simulated)`})
      await refresh()
      notify('Exit gate approved. Demo receipt created; no money charged.')
    } catch(e) {
      setExitOutcome({approved:false, message:e.message || 'Exit review required'})
      await refresh()
    } finally {setBusy(false)}
  }
  const scan = (barcode) => action('/scan',{barcode:barcode.trim()},'Product scanned. Cart updated.')
  const products = data?.products || []
  const totalQty = products.reduce((a,b)=>a+b.scanned_qty,0)
  const discrepancies = data?.discrepancy_count || 0
  const fusionPending = data?.fusion?.blocked || false
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><ShoppingBasket size={23}/></div><div><strong>smartcart<span>.ai</span></strong><small>RETAIL INTELLIGENCE</small></div></div>
      <div className="side-section">YOUR STORE</div>
      <nav className="side-nav">
        <button className={tab==='shopper'?'active':''} onClick={()=>setTab('shopper')}><Smartphone size={19}/> Shopper app <ChevronRight size={17}/></button>
        <button className={tab==='operations'?'active':''} onClick={()=>setTab('operations')}><Eye size={19}/> Shelf operations <ChevronRight size={17}/></button>
      </nav>
      <div className="sidebar-bottom"><div className="live-tag"><span className="live-pulse"/> DEMO SESSION</div><p>One shopper · Three sample products<br/>No real payment is processed</p></div>
    </aside>
    <main className="main">
      <header className="topbar"><div><span className="crumb">SmartCart AI</span><ChevronRight size={15}/><strong>{tab==='shopper'?'Shopper app':'Shelf operations'}</strong></div><span className={`top-status ${data?'connected':'checking'}`}><span className="status-dot"/> {data?'Session connected':'Connecting to demo session'}</span></header>
      <div className="content">
        <section className={`hero ${tab==='shopper'?'shopper-hero':'operations-hero'}`}><div><div className="hero-tag">PICK · SCAN · GO · SECURELY</div><h1>{tab==='shopper'?'Your trip, ready to go.':'Shelf activity, in view.'}</h1><p>{tab==='shopper'?'Scan what you pick up. Your cart checks each item against shelf activity before simulated checkout.':'Monitor the demo shelf, review camera observations, and reconcile activity with the shopper cart.'}</p></div><div className="hero-graphic"><ShieldCheck size={42}/><span>DEMO<br/>SESSION</span></div></section>
        {error && <div className="global-error"><CircleAlert size={18}/> {error}<button onClick={()=>setError('')}><X size={17}/></button></div>}
        <div className="session-ribbon" aria-label="Shopping session summary">
          <span><ShoppingBasket size={16}/><b>{totalQty}</b> {totalQty===1?'item':'items'} scanned</span>
          <i aria-hidden="true"/>
          <span className={discrepancies?'needs-review':''}>{discrepancies?<CircleAlert size={16}/>:<BadgeCheck size={16}/>}<b>{discrepancies|| (data?.verified?'Verified':'Ready')}</b> {discrepancies?'to review':data?.verified?'cart match':'cart check'}</span>
          <i aria-hidden="true"/>
          <span><CreditCard size={16}/><b>{money(data?.total_paise||0)}</b> mock total</span>
          {fusionPending&&<span className="ribbon-pending"><CircleAlert size={15}/> Sensor evidence pending</span>}
        </div>
        {tab==='shopper' ? <>
          <div className="two-col shopper-workspace">
            <div className="panel scan-panel"><div className="panel-head"><div><div className="eyebrow">SHOPPING SESSION · DEMO STORE #001</div><h2>Scan an item</h2></div><span className="pill muted"><span className="status-dot"/> Ready to scan</span></div>
              <p className="scan-intro">Scan each item’s barcode as you shop. Keep quantities matched to enable checkout.</p>
              <div className="scan-mode-switch" role="group" aria-label="Barcode scan method"><button className="active" type="button" onClick={()=>setScanner(true)}><ScanLine size={17}/> Scan barcode</button><button type="button" onClick={()=>document.getElementById('manual-barcode')?.focus()}><Barcode size={17}/> Enter barcode</button></div>
              <div className="scan-placeholder"><div className="scan-icon"><ScanLine size={34}/></div><h3>Point your camera at the item’s barcode</h3><p>The camera will ask permission to scan barcodes using your device.</p></div>
              <button className="btn primary wide scan-open" onClick={()=>setScanner(true)}><Camera size={18}/> Open camera scanner</button>
              <div className="manual-entry"><form onSubmit={e=>{e.preventDefault();if(manual.trim()){scan(manual);setManual('')}}}><label htmlFor="manual-barcode">Or enter barcode number</label><div><div className="barcode-input-wrap"><Barcode size={18}/><input id="manual-barcode" value={manual} onChange={e=>setManual(e.target.value)} placeholder="Enter barcode number"/></div><button className="btn secondary" type="submit" disabled={busy}>Add</button></div></form></div>
              <p className="scan-helper"><Info size={15}/> No camera? Enter a printed demo barcode. To record a pickup first, open <button type="button" onClick={()=>setTab('operations')}>Shelf operations</button>.</p>
            </div>
            <div className="panel cart-panel"><div className="panel-head"><div><h2>Your cart <span className="cart-count">{totalQty} {totalQty===1?'item':'items'}</span></h2></div><span className="demo-data-label">All values are demo data.</span></div>
              <div className="cart-table-wrap"><table className="cart-table"><thead><tr><th>Item</th><th>Price</th><th>Physical qty</th><th>Scanned qty</th><th>Status</th><th>Action</th></tr></thead><tbody>{products.filter(p=>p.physical_qty||p.scanned_qty).map(p=><tr key={p.id}><td><span className="table-product"><span className="product-emoji">{p.emoji}</span><span><strong>{p.name}</strong><small>{p.zone==='SIM'?'Simulated shelf':`Shelf ${p.zone}`}</small></span></span></td><td>{p.price_pending?'Price pending':money(p.price_paise)}</td><td>{p.physical_qty}</td><td>{p.scanned_qty}</td><td><span className={`pill tiny ${classNameFor(p.status)}`}>{labelFor(p.status)}</span></td><td>{p.scanned_qty>p.physical_qty?<button title={`Remove one extra scan of ${p.name}`} className="row-action" disabled={busy} onClick={()=>action('/unscan',{product_id:p.id},'Removed one extra scan')}>Remove scan</button>:p.physical_qty>p.scanned_qty?<button title={`Scan ${p.name}`} className="row-action emphasized" disabled={busy} onClick={()=>scan(p.barcode)}>Scan item</button>:<span className="no-row-action">—</span>}</td></tr>)}</tbody></table></div>
              {!products.some(p=>p.physical_qty||p.scanned_qty)&&<div className="cart-empty">Your cart is empty. Scan a sample product to start.</div>}
              {discrepancies>0&&<div className="cart-recovery" role="status"><CircleAlert size={17}/><span><b>{discrepancies} item mismatch{discrepancies===1?'':'es'} to resolve.</b> Review shelf activity, then scan or remove the matching item.</span><button className="btn secondary" onClick={()=>setTab('operations')}>Review shelf activity <ArrowRight size={15}/></button></div>}
              {fusionPending && <div className="note danger"><CircleAlert size={16}/> Sensor evidence needs a matching camera and simulated weight event before checkout.</div>}
              <div className="cart-checkout-summary"><div className="total-line"><span>Total <small>({totalQty} {totalQty===1?'item':'items'})</small></span><strong>{money(data?.total_paise||0)}</strong></div><div className="checkout-action"><button className="btn primary wide checkout" disabled={busy||!!data?.receipt||!data?.billing_ready} onClick={()=>action('/checkout',undefined,'Mock checkout completed!')}><CreditCard size={18}/>{data?.receipt?'Checkout complete':data?.verified&&!data?.billing_ready?'Price needed for checkout':'Proceed to checkout'} <ArrowRight size={17}/></button><p className="small muted">{data?.price_pending_count?'A confirmed price is needed for each scanned prototype product.':data?.verified?'Cart quantities match. Payment is simulated.':'Please resolve item count differences to continue to checkout.'}</p></div></div>
              {data?.receipt && <div className="receipt"><FileCheck2 size={21}/><div><strong>{data.receipt.id}</strong><span>Payment simulated · {money(data.receipt.total_paise)} · No money charged</span></div></div>}
            </div>
          </div>
          <div className="panel exit-panel">
            <div className="panel-head"><div><div className="eyebrow">PHASE 6 · AUTOMATED EXIT DEMONSTRATION</div><h2>Exit gate simulator</h2></div>
              <span className={`pill ${data?.exit?.state==='READY'||data?.exit?.state==='COMPLETED'?'success':'warning'}`}>{data?.exit?.state?.replace('_',' ')||'WAITING'}</span>
            </div>
            <p className="muted small">This button simulates an exit sensor. It cross-checks both carts and pending sensor evidence. If verified, it issues one <b>mock</b> receipt; otherwise it blocks and records why. No real exit camera, gate, or payment is connected.</p>
            <div className="exit-flow">
              <span><ShieldCheck size={16}/> Physical / scanned cart</span><ArrowRight size={15}/><span><Scale size={16}/> Sensor evidence</span><ArrowRight size={15}/><span><CreditCard size={16}/> Mock billing</span>
            </div>
            <div className="exit-decision"><strong>{data?.exit?.state==='COMPLETED'?'Mock payment complete':data?.exit?.state==='READY'?'Ready for exit':'Exit requires review'}</strong><span>{data?.exit?.reason}</span></div>
            <button className="btn primary" onClick={exitAttempt} disabled={busy}><DoorOpen size={18}/>{busy?'Checking…':'Simulate customer reaching exit'}<ArrowRight size={17}/></button>
            {exitOutcome && <div role="status" className={`note ${exitOutcome.approved?'good':'danger'}`}>
              {exitOutcome.approved?<CheckCircle2 size={17}/>:<CircleAlert size={17}/>} {exitOutcome.message}
            </div>}
          </div>
          <details className="inventory-details"><summary>Shopper products and demo barcodes <span>{products.length} products · tap Demo scan to try</span></summary><div className="panel product-panel"><p className="muted small">Prototype product barcodes are generated for this demo only. Add confirmed prices before checkout.</p><div className="products-grid">{products.map(p=><div className="product-tile" key={p.id}><div className="tile-top"><div className="tile-emoji">{p.emoji}</div><span>{p.zone==='SIM'?'SIMULATED PICKUP':`ZONE ${p.zone}`}</span></div><h3>{p.name}</h3><p>{p.demo_barcode?'Demo code only: ':'Barcode: '}{p.barcode}</p><div className="tile-bottom"><b>{p.price_pending?'Price pending':money(p.price_paise)}</b><button className="tiny-text-btn" onClick={()=>scan(p.barcode)} disabled={busy}>Demo scan <Plus size={15}/></button></div></div>)}</div></div></details>
        </> : <>
          <div className="two-col operations-grid"><CameraPanel refresh={refresh} notify={notify} products={products.filter(p=>['A','B','C'].includes(p.zone))} sku={data?.sku}/><div className="panel"><div className="panel-head"><div><div className="eyebrow">NO HARDWARE NEEDED</div><h2>Simulate shelf events</h2></div><span className="pill muted">MANUAL TESTING</span></div><p className="muted">Use these controls when your webcam isn't available. Each click represents one actual item being picked up or returned.</p>
            <div className="sim-products">{products.map(p=><div className="sim-row" key={p.id}><div className="product-emoji">{p.emoji}</div><div className="sim-name"><strong>{p.name}</strong><small>{p.zone==='SIM'?'Simulated shelf':`Zone ${p.zone}`} · Physical qty {p.physical_qty}</small></div><button className="btn small-btn secondary" disabled={busy||!!data?.receipt||data?.fusion?.enabled} onClick={()=>action('/simulate',{product_id:p.id,action:'return'},`${p.name} returned`)}><Minus size={15}/> Return</button><button className="btn small-btn primary" disabled={busy||!!data?.receipt||data?.fusion?.enabled} onClick={()=>action('/simulate',{product_id:p.id,action:'pickup'},`${p.name} picked up`)}><Plus size={15}/> Pickup</button></div>)}</div>
            <div className="tip"><Info size={17}/> Manual cart changes are disabled in two-signal mode. Use the fusion camera and weight controls below instead.</div>
          </div></div>
          <details className="operations-advanced"><summary>Sensor fusion controls <span>Requires simulated shelf weight · prototype</span></summary><FusionPanel data={data} action={action} busy={busy}/></details>
          <details className="operations-advanced"><summary>Print sample product labels <span>Use these barcodes to demonstrate scan-to-cart</span></summary><div className="panel labels-panel"><div className="panel-head"><div><div className="eyebrow">PRINTABLE TEST LABELS</div><h2>Demo barcodes</h2></div><button className="btn secondary" onClick={()=>setShowLabels(v=>!v)}><Barcode size={17}/>{showLabels?'Hide labels':'Show labels'}</button></div>
            <p className="muted small">Print these EAN-13 labels to try scanning. Prototype product codes work only in this app and are not retail barcodes.</p>
            {showLabels&&<><div className="barcode-grid">{products.map(p=><BarcodeLabel key={p.id} product={p}/>)}</div><button className="btn secondary print-button" onClick={()=>window.print()}>Print product labels</button></>}
          </div></details>
        </>}
        {tab==='shopper'&&<details className="demo-guide-details"><summary>Five-minute guided demo <span>Optional walkthrough and session reset</span></summary><DemoGuide data={data} tab={tab} setTab={setTab} action={action} busy={busy}/></details>}
        <div className="panel events-panel"><div className="panel-head"><div><div className="eyebrow">SESSION RECORD</div><h2>Shopping activity</h2></div><button className="btn secondary" onClick={()=>{if(window.confirm('Start a new demo session? Restock the 3 camera zones first.'))action('/reset',undefined,'New demo session ready')}}><RefreshCw size={16}/> Reset session</button></div>
          <div className="event-feed">{data?.events?.length ? data.events.slice(0,8).map(e=><div className="event" key={e.id}><div className="event-dot"><Activity size={16}/></div><div><strong>{e.message}</strong><p>{e.source.toUpperCase()} · {e.kind}</p></div><time>{new Date(e.created_at).toLocaleTimeString()}</time></div>) : <div className="no-events">No events yet. Start a shelf pickup or scan a product.</div>}</div>
        </div>
        <footer>SmartCart AI · Hackathon prototype · One active demo session · Simulated billing only</footer>
      </div>
    </main>
    {notice && <div className="toast" role="status" aria-live="polite"><CheckCircle2 size={17}/>{notice}</div>}
    {scanner && <Scanner onClose={()=>setScanner(false)} onScan={scan}/>}
  </div>
}
export default App
