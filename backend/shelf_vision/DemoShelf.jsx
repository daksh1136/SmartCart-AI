// DemoShelf.jsx - plays the recorded shelf video through the real model on the backend.
//
// Usage (e.g. on the "Shelf operations" page):
//   <DemoShelf apiBase="https://YOUR-BACKEND.onrender.com" sessionId={sessionId}
//              onEvent={(ev) => refreshCart()} />
//
// Every frame is sent to GET /vision/demo/step. The backend runs the trained model,
// returns what it sees in each zone, and applies any pickup/return to the cart.

import { useEffect, useRef, useState } from "react";

const COLORS = { empty: "#9ca3af", hand: "#f59e0b", uncertain: "#ef4444" };

export default function DemoShelf({ apiBase = "", sessionId = "demo", onEvent }) {
  const [config, setConfig] = useState(null);
  const [info, setInfo] = useState(null);
  const [frame, setFrame] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [log, setLog] = useState([]);
  const [error, setError] = useState("");
  const idx = useRef(0);
  const playingRef = useRef(false);

  useEffect(() => {
    Promise.all([
      fetch(`${apiBase}/vision/config`).then((r) => r.json()),
      fetch(`${apiBase}/vision/demo/info`).then((r) => r.json()),
    ])
      .then(([c, i]) => { setConfig(c); setInfo(i); })
      .catch(() => setError("Could not reach the shelf vision API"));
  }, [apiBase]);

  async function loop() {
    const delay = 1000 / (info?.fps || 8);
    while (playingRef.current) {
      const started = performance.now();
      try {
        const url = `${apiBase}/vision/demo/step?i=${idx.current}&session_id=${encodeURIComponent(sessionId)}`;
        const r = await fetch(url).then((res) => res.json());
        setFrame(r);
        if (r.events?.length) {
          setLog((old) => [...r.events.map((e) => ({ ...e, t: new Date().toLocaleTimeString() })), ...old].slice(0, 20));
          r.events.forEach((e) => onEvent && onEvent(e));
        }
        if (r.done) { stop(); break; }
        idx.current += 1;
      } catch {
        setError("Lost connection to the backend"); stop(); break;
      }
      const wait = delay - (performance.now() - started);
      if (wait > 0) await new Promise((res) => setTimeout(res, wait));
    }
  }

  function play() {
    if (playingRef.current || !info) return;
    if (frame?.done) restart(false);
    playingRef.current = true; setPlaying(true); setError("");
    loop();
  }
  function stop() { playingRef.current = false; setPlaying(false); }
  function restart(autoplay = true) {
    stop(); idx.current = 0; setLog([]); setFrame(null);
    if (autoplay) setTimeout(play, 50);
  }

  const W = config?.width || 640, H = config?.height || 480;

  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, padding: 16, background: "#fff" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 12, letterSpacing: 1, color: "#6b7280" }}>SHELF CAMERA · AI VISION</div>
          <div style={{ fontWeight: 600, fontSize: 18 }}>Recorded shelf, analysed live by our model</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {!playing ? <button onClick={play} disabled={!info}>▶ Play</button> : <button onClick={stop}>⏸ Pause</button>}
          <button onClick={() => restart(true)} disabled={!info}>↺ Restart</button>
        </div>
      </div>

      {error && <div style={{ color: "#b91c1c", marginBottom: 8 }}>{error}</div>}

      <div style={{ position: "relative", width: "100%", aspectRatio: `${W} / ${H}`, background: "#111", borderRadius: 8, overflow: "hidden" }}>
        {frame?.image
          ? <img src={frame.image} alt="shelf" style={{ width: "100%", height: "100%", display: "block" }} />
          : <div style={{ color: "#9ca3af", display: "grid", placeItems: "center", height: "100%" }}>Press Play to start the shelf camera</div>}
        {config?.zones.map((z, k) => {
          const p = frame?.zones?.[k];
          const label = p ? (p.confidence < 0.6 ? "uncertain" : p.label) : z.product;
          const color = COLORS[label] || "#16a34a";
          return (
            <div key={z.name} style={{
              position: "absolute", left: `${(z.x / W) * 100}%`, top: `${(z.y / H) * 100}%`,
              width: `${(z.w / W) * 100}%`, height: `${(z.h / H) * 100}%`,
              border: `3px solid ${color}`, borderRadius: 4, boxSizing: "border-box",
            }}>
              <span style={{ background: color, color: "#fff", fontSize: 12, padding: "2px 6px", borderRadius: "0 0 4px 0" }}>
                {z.name}: {label}{p ? ` ${Math.round(p.confidence * 100)}%` : ""}
              </span>
            </div>
          );
        })}
      </div>

      <div style={{ marginTop: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>Detected shelf events</div>
        {log.length === 0 && <div style={{ color: "#6b7280" }}>No pickups yet.</div>}
        {log.map((e, k) => (
          <div key={k} style={{ fontSize: 14, padding: "4px 0", borderBottom: "1px solid #f3f4f6" }}>
            <b style={{ color: e.event_type === "pickup" ? "#b45309" : "#047857" }}>
              {e.event_type === "pickup" ? "PICKUP" : "RETURN"}
            </b>{" "}{e.product} · zone {e.zone} · {Math.round(e.confidence * 100)}% · {e.t}
          </div>
        ))}
      </div>
    </div>
  );
}
