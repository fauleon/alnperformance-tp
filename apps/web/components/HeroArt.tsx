"use client";

import { useEffect, useRef, useState } from "react";

type Point = { x: number; y: number };
type Particle = { from: 0 | 1; t: number; speed: number; rejected: boolean; size: number };

const SOURCES: Point[] = [{ x: 0.12, y: 0.28 }, { x: 0.12, y: 0.72 }];
const GATE: Point = { x: 0.54, y: 0.5 };
const TARGET: Point = { x: 0.88, y: 0.5 };
const REJECT: Point = { x: 0.66, y: 0.94 };
const COLORS = ["#8ab4ff", "#ff7eb6"];
const FPS = 24;

function bezier(a: Point, b: Point, t: number, bend: number): Point {
  const c1 = { x: a.x + (b.x - a.x) * 0.45, y: a.y + bend };
  const c2 = { x: a.x + (b.x - a.x) * 0.7, y: b.y };
  const u = 1 - t;
  return {
    x: u * u * u * a.x + 3 * u * u * t * c1.x + 3 * u * t * t * c2.x + t * t * t * b.x,
    y: u * u * u * a.y + 3 * u * u * t * c1.y + 3 * u * t * t * c2.y + t * t * t * b.y,
  };
}

function position(p: Particle): Point {
  if (p.t <= 1) return bezier(SOURCES[p.from], GATE, p.t, p.from === 0 ? -0.06 : 0.06);
  return bezier(GATE, p.rejected ? REJECT : TARGET, p.t - 1, p.rejected ? 0.12 : 0);
}

function spawn(): Particle {
  return { from: Math.random() < 0.55 ? 0 : 1, t: 0, speed: 0.006 + Math.random() * 0.006, rejected: Math.random() < 0.22, size: 1.6 + Math.random() * 2 };
}

export function HeroArt() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [paused, setPaused] = useState(false);
  const [canAnimate, setCanAnimate] = useState(false);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const saveData = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData === true;
    const animate = !reduce && !saveData;
    setCanAnimate(animate);

    let width = 0, height = 0, frame = 0, last = 0, visible = true;
    const particles: Particle[] = Array.from({ length: 34 }, () => ({ ...spawn(), t: Math.random() * 2 }));

    const resize = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      const rect = canvas.getBoundingClientRect();
      width = rect.width; height = rect.height;
      canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      draw();
    };

    const px = (p: Point) => ({ x: p.x * width, y: p.y * height });

    function draw() {
      ctx!.clearRect(0, 0, width, height);
      ctx!.fillStyle = "#ffffff10";
      for (let x = 24; x < width; x += 28) for (let y = 24; y < height; y += 28) ctx!.fillRect(x, y, 1.2, 1.2);
      // Paths
      ctx!.lineWidth = 1.2;
      for (const [from, to, bend, color] of [[SOURCES[0], GATE, -0.06, "#8ab4ff40"], [SOURCES[1], GATE, 0.06, "#ff7eb640"], [GATE, TARGET, 0, "#dafa7366"], [GATE, REJECT, 0.12, "#ff7b7b33"]] as const) {
        ctx!.strokeStyle = color;
        ctx!.beginPath();
        for (let i = 0; i <= 40; i++) {
          const p = px(bezier(from, to, i / 40, bend));
          if (i === 0) ctx!.moveTo(p.x, p.y); else ctx!.lineTo(p.x, p.y);
        }
        ctx!.stroke();
      }
      // Nodes
      SOURCES.forEach((source, i) => {
        const p = px(source);
        ctx!.fillStyle = COLORS[i];
        ctx!.beginPath(); ctx!.arc(p.x, p.y, 9, 0, Math.PI * 2); ctx!.fill();
        ctx!.strokeStyle = COLORS[i] + "55"; ctx!.lineWidth = 8;
        ctx!.beginPath(); ctx!.arc(p.x, p.y, 16, 0, Math.PI * 2); ctx!.stroke();
      });
      const gate = px(GATE);
      ctx!.save(); ctx!.translate(gate.x, gate.y); ctx!.rotate(Math.PI / 4);
      ctx!.strokeStyle = "#dafa73"; ctx!.lineWidth = 2; ctx!.fillStyle = "#11111b";
      ctx!.fillRect(-20, -20, 40, 40); ctx!.strokeRect(-20, -20, 40, 40);
      ctx!.restore();
      ctx!.fillStyle = "#dafa73"; ctx!.beginPath(); ctx!.arc(gate.x, gate.y, 4, 0, Math.PI * 2); ctx!.fill();
      const target = px(TARGET);
      ctx!.fillStyle = "#dafa73"; ctx!.beginPath(); ctx!.arc(target.x, target.y, 12, 0, Math.PI * 2); ctx!.fill();
      ctx!.strokeStyle = "#dafa7340"; ctx!.lineWidth = 10; ctx!.beginPath(); ctx!.arc(target.x, target.y, 22, 0, Math.PI * 2); ctx!.stroke();
      const reject = px(REJECT);
      ctx!.strokeStyle = "#ff7b7b"; ctx!.lineWidth = 2;
      ctx!.beginPath(); ctx!.moveTo(reject.x - 7, reject.y - 7); ctx!.lineTo(reject.x + 7, reject.y + 7); ctx!.moveTo(reject.x + 7, reject.y - 7); ctx!.lineTo(reject.x - 7, reject.y + 7); ctx!.stroke();
      // Particles
      for (const particle of particles) {
        const p = px(position(particle));
        ctx!.fillStyle = particle.t > 1 ? (particle.rejected ? "#ff7b7b" : "#dafa73") : COLORS[particle.from];
        ctx!.globalAlpha = particle.t > 1.85 ? Math.max(0, (2 - particle.t) / 0.15) : 1;
        ctx!.beginPath(); ctx!.arc(p.x, p.y, particle.size, 0, Math.PI * 2); ctx!.fill();
      }
      ctx!.globalAlpha = 1;
    }

    function tick(now: number) {
      frame = requestAnimationFrame(tick);
      if (pausedRef.current || !visible || document.hidden || now - last < 1000 / FPS) return;
      last = now;
      for (const particle of particles) {
        particle.t += particle.speed * (particle.t > 1 ? 1.3 : 1);
        if (particle.t >= 2) Object.assign(particle, spawn());
      }
      draw();
    }

    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    const io = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; }, { threshold: 0.05 });
    io.observe(canvas);
    resize();
    if (animate) frame = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(frame); observer.disconnect(); io.disconnect(); };
  }, []);

  return <div className="hero-art">
    <canvas ref={canvasRef} role="img" aria-label="Sinais do Google Ads e do TikTok Ads passam pela política de segurança; só o que você aprova segue para as plataformas, o resto é barrado."/>
    <div className="art-legend" aria-hidden="true">
      <span><i className="legend-google"/>Google Ads</span>
      <span><i className="legend-tiktok"/>TikTok Ads</span>
      <span><i className="legend-ok"/>Aprovado por você</span>
      <span><i className="legend-bad"/>Barrado pela política</span>
    </div>
    {canAnimate && <button type="button" className="art-pause" aria-pressed={paused} onClick={() => setPaused(value => !value)}>{paused ? "▶ Retomar animação" : "❚❚ Pausar animação"}</button>}
  </div>;
}
