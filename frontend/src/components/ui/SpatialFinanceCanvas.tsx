// SpatialFinanceCanvas — Multi-Layered 3D Financial Reconciliation Space
// Renders 3 distinct Z-depth layers:
// Layer 1 (Distant Z=0.2): Blurred financial fragments, ledger codes, slow drift.
// Layer 2 (Mid-Depth Z=0.5): Transaction rows, fee schedules, bank statement snippets.
// Layer 3 (Near-Background Z=0.85): The Reconciliation Connection Network
//   (Invoice \ + Settlement -> Match Node -> Verify/Review/Unresolved paths).
// Pure GPU Canvas2D + requestAnimationFrame; cursor parallax + scroll depth; respects prefers-reduced-motion.

import React, { useEffect, useRef } from 'react';
import { useApp } from '../../store/AppContext';

interface DistantFragment {
  x: number;
  y: number;
  vx: number;
  vy: number;
  text: string;
  subText?: string;
  opacity: number;
  scale: number;
}

interface MidTransactionRecord {
  x: number;
  y: number;
  vx: number;
  ref: string;
  amount: string;
  category: string;
  type: 'invoice' | 'settlement' | 'bank';
  status: string;
  width: number;
  opacity: number;
}

interface ReconciliationBranch {
  // Source nodes
  invX: number;
  invY: number;
  setX: number;
  setY: number;
  bnkX: number;
  bnkY: number;
  // Match node
  matchX: number;
  matchY: number;
  // Destination
  destX: number;
  destY: number;
  type: 'verified' | 'review' | 'unresolved';
  label: string;
  progress: number;
  speed: number;
  pulseSize: number;
}

export function SpatialFinanceCanvas() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const { currentRun, runStatus, selectedResult } = useApp();
  const isRunning = runStatus === 'running';
  const hasSelectedResult = !!selectedResult;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d', { alpha: true });
    if (!ctx) return;

    // Check reduced motion
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    let animId: number;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    // Mouse Parallax target and current
    let mouseX = width / 2;
    let mouseY = height / 2;
    let targetParallaxX = 0;
    let targetParallaxY = 0;
    let currentParallaxX = 0;
    let currentParallaxY = 0;

    // Scroll depth tracking
    let scrollY = window.scrollY || 0;
    let targetScrollY = scrollY;
    let currentScrollY = scrollY;

    const handleMouseMove = (e: MouseEvent) => {
      mouseX = e.clientX;
      mouseY = e.clientY;
      targetParallaxX = (mouseX / width - 0.5);
      targetParallaxY = (mouseY / height - 0.5);
    };

    const handleScroll = () => {
      targetScrollY = window.scrollY || 0;
    };

    const handleResize = () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
      initNetwork();
    };

    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    window.addEventListener('scroll', handleScroll, { passive: true });
    window.addEventListener('resize', handleResize, { passive: true });

    // =========================================================================
    // LAYER 1: DISTANT FINANCIAL DATA SPACE (Z = 0.2)
    // Tiny, blurred fragments drifting slowly across deep background
    // =========================================================================
    const distantTokens = [
      { text: 'INV-2026045', sub: '₹29,700' },
      { text: 'SET-8821', sub: '₹17,820' },
      { text: 'BANK VERIFIED', sub: 'UTR-89102' },
      { text: 'TXN-48392', sub: '04 SEP' },
      { text: '₹2,91,600', sub: 'GROSS' },
      { text: 'MATCHED', sub: 'CONF 98%' },
      { text: 'PENDING', sub: 'SLA T+2' },
      { text: 'LEDGER ACCT', sub: 'CR 104' },
      { text: 'SETTLEMENT', sub: 'AUTOCLEAR' },
      { text: '+₹84,500', sub: 'NEFT' },
      { text: '-₹1,240', sub: 'MDR FEE' },
      { text: 'REF-38472', sub: 'ORDER 109' },
      { text: 'GST DEDUCT', sub: '18% CGST' },
      { text: 'BILL-2026057', sub: 'VARIANCE' },
      { text: 'BNK-2026-0038', sub: '₹10,045' },
      { text: 'PAYMENT GATEWAY', sub: 'RAZORPAY' },
      { text: '₹3,54,000', sub: 'UNRESOLVED' },
      { text: 'EXACT MATCH', sub: '100% PAIR' },
      { text: 'AUDIT LOGGED', sub: 'HASH-SHA256' },
    ];

    const distantFragments: DistantFragment[] = distantTokens.map(t => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.15,
      vy: (Math.random() - 0.5) * 0.12,
      text: t.text,
      subText: t.sub,
      opacity: 0.05 + Math.random() * 0.06,
      scale: 0.8 + Math.random() * 0.3,
    }));

    // =========================================================================
    // LAYER 2: MOVING TRANSACTION LEDGER SNIPPETS (Z = 0.5)
    // Structured credit/debit slips and ledger tracks
    // =========================================================================
    const midTokens = [
      { ref: 'INV-BILL-2026012', amount: '₹54,000.00', category: 'ENTERPRISE SAAS', type: 'invoice' as const, status: 'MATCHED' },
      { ref: 'SET-SET-2026012', amount: '₹52,920.00', category: 'GATEWAY NET (-2%)', type: 'settlement' as const, status: 'MATCHED' },
      { ref: 'BNK-TXN-2026012', amount: '₹52,920.00', category: 'HDFC ESCROW CR', type: 'bank' as const, status: 'VERIFIED' },
      { ref: 'INV-BILL-2026042', amount: '₹10,250.00', category: 'MONTHLY SUB', type: 'invoice' as const, status: 'EXACT' },
      { ref: 'SET-SET-2026042', amount: '₹10,045.00', category: 'MDR ADJUSTED', type: 'settlement' as const, status: 'EXACT' },
      { ref: 'INV-BILL-2026053', amount: '₹2,91,600.00', category: 'ANNUAL CONTRACT', type: 'invoice' as const, status: 'DELAYED' },
      { ref: 'BNK-TXN-2026053', amount: '₹2,85,768.00', category: 'AXIS CLEARING', type: 'bank' as const, status: 'DELAYED' },
      { ref: 'INV-BILL-2026057', amount: '₹2,04,400.00', category: 'MISSING GATEWAY', type: 'invoice' as const, status: 'UNRESOLVED' },
    ];

    const midRecords: MidTransactionRecord[] = midTokens.map((m, idx) => ({
      x: (idx / midTokens.length) * width + Math.random() * 100,
      y: 120 + (idx % 4) * (height / 4) + (Math.random() - 0.5) * 60,
      vx: 0.18 + (idx % 3) * 0.08,
      ref: m.ref,
      amount: m.amount,
      category: m.category,
      type: m.type,
      status: m.status,
      width: 170,
      opacity: 0.12 + Math.random() * 0.06,
    }));

    // =========================================================================
    // LAYER 3: RECONCILIATION CONNECTION NETWORK (Z = 0.85)
    // 3-way spatial paths: Invoice + Settlement + Bank -> Match Node -> Outcome
    // =========================================================================
    let networkBranches: ReconciliationBranch[] = [];

    const initNetwork = () => {
      networkBranches = [
        // Verified Stream 1 (Upper)
        {
          invX: width * 0.08,
          invY: height * 0.22,
          setX: width * 0.22,
          setY: height * 0.28,
          bnkX: width * 0.15,
          bnkY: height * 0.35,
          matchX: width * 0.46,
          matchY: height * 0.28,
          destX: width * 0.88,
          destY: height * 0.25,
          type: 'verified',
          label: 'AUTO-VERIFIED [₹54,000]',
          progress: 0.2,
          speed: 0.0014,
          pulseSize: 2.5,
        },
        // Verified Stream 2 (Mid-Lower)
        {
          invX: width * 0.12,
          invY: height * 0.62,
          setX: width * 0.26,
          setY: height * 0.55,
          bnkX: width * 0.18,
          bnkY: height * 0.72,
          matchX: width * 0.50,
          matchY: height * 0.60,
          destX: width * 0.86,
          destY: height * 0.52,
          type: 'verified',
          label: 'AUTO-VERIFIED [₹10,250]',
          progress: 0.65,
          speed: 0.0012,
          pulseSize: 2.5,
        },
        // Review Required Stream (Branches amber outward)
        {
          invX: width * 0.10,
          invY: height * 0.44,
          setX: width * 0.24,
          setY: height * 0.42,
          bnkX: width * 0.16,
          bnkY: height * 0.48,
          matchX: width * 0.48,
          matchY: height * 0.44,
          destX: width * 0.82,
          destY: height * 0.76,
          type: 'review',
          label: 'REVIEW REQUIRED [PARTIAL]',
          progress: 0.4,
          speed: 0.001,
          pulseSize: 2.5,
        },
        // Unresolved Stream (Fades into red terminus)
        {
          invX: width * 0.14,
          invY: height * 0.82,
          setX: width * 0.28,
          setY: height * 0.86,
          bnkX: width * 0.20,
          bnkY: height * 0.88,
          matchX: width * 0.52,
          matchY: height * 0.84,
          destX: width * 0.78,
          destY: height * 0.92,
          type: 'unresolved',
          label: 'UNRESOLVED [NO FEED]',
          progress: 0.85,
          speed: 0.0008,
          pulseSize: 2.5,
        },
      ];
    };

    initNetwork();

    let lastTime = performance.now();

    // =========================================================================
    // MAIN RENDER LOOP
    // =========================================================================
    const render = (time: number) => {
      if (document.hidden) {
        animId = requestAnimationFrame(render);
        return;
      }

      const dt = Math.min(32, time - lastTime);
      lastTime = time;

      // Smooth interpolation for mouse parallax & scroll depth
      currentParallaxX += (targetParallaxX - currentParallaxX) * 0.06;
      currentParallaxY += (targetParallaxY - currentParallaxY) * 0.06;
      currentScrollY += (targetScrollY - currentScrollY) * 0.08;

      ctx.clearRect(0, 0, width, height);

      // Speed factor: 2.5x during active run, 0.35x when inspecting drawer, 1.0x normal
      const speedMultiplier = isRunning ? 2.5 : hasSelectedResult ? 0.35 : 1.0;

      // -----------------------------------------------------------------------
      // LAYER 1: DISTANT FINANCIAL DATA SPACE (Z = 0.2)
      // Parallax rate: 2px mouse, 0.08x scroll
      // -----------------------------------------------------------------------
      const l1ParallaxX = currentParallaxX * 8;
      const l1ParallaxY = currentParallaxY * 8 - (currentScrollY * 0.05);

      // Faint 3D perspective grid lines
      ctx.strokeStyle = 'rgba(30, 41, 59, 0.14)';
      ctx.lineWidth = 0.75;
      const gridGapY = 56;
      const gridOffsetY = (l1ParallaxY % gridGapY);
      for (let y = gridOffsetY; y < height; y += gridGapY) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // Vertical ledger column balance guides
      ctx.strokeStyle = 'rgba(30, 41, 59, 0.08)';
      ctx.setLineDash([2, 6]);
      const gridGapX = 140;
      const gridOffsetX = (l1ParallaxX % gridGapX);
      for (let x = gridOffsetX; x < width; x += gridGapX) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      ctx.setLineDash([]);

      // Draw Distant Text Fragments
      ctx.font = '8px "JetBrains Mono", monospace';
      distantFragments.forEach(frag => {
        if (!prefersReducedMotion) {
          frag.x += frag.vx * speedMultiplier;
          frag.y += frag.vy * speedMultiplier;

          if (frag.x < -100) frag.x = width + 100;
          if (frag.x > width + 100) frag.x = -100;
          if (frag.y < -50) frag.y = height + 50;
          if (frag.y > height + 50) frag.y = -50;
        }

        const drawX = frag.x + l1ParallaxX;
        const drawY = frag.y + l1ParallaxY;

        ctx.fillStyle = `rgba(100, 116, 139, ${frag.opacity})`;
        ctx.fillText(frag.text, drawX, drawY);
        if (frag.subText) {
          ctx.fillStyle = `rgba(71, 85, 105, ${frag.opacity * 0.8})`;
          ctx.fillText(frag.subText, drawX, drawY + 9);
        }
      });

      // -----------------------------------------------------------------------
      // LAYER 2: MOVING LEDGER & TRANSACTION SLIPS (Z = 0.5)
      // Parallax rate: 5px mouse, 0.15x scroll
      // -----------------------------------------------------------------------
      const l2ParallaxX = currentParallaxX * 16;
      const l2ParallaxY = currentParallaxY * 16 - (currentScrollY * 0.12);

      midRecords.forEach(rec => {
        if (!prefersReducedMotion) {
          rec.x += rec.vx * speedMultiplier;
          if (rec.x > width + 100) {
            rec.x = -rec.width - 40;
          }
        }

        const drawX = rec.x + l2ParallaxX;
        const drawY = rec.y + l2ParallaxY;

        // Skip if outside viewport
        if (drawX < -rec.width || drawX > width + 60 || drawY < -40 || drawY > height + 40) return;

        // Subtle micro ledger slip container
        ctx.fillStyle = 'rgba(15, 23, 42, 0.45)';
        ctx.strokeStyle = rec.type === 'invoice'
          ? 'rgba(56, 189, 248, 0.12)'
          : rec.type === 'settlement'
          ? 'rgba(99, 102, 241, 0.12)'
          : 'rgba(16, 185, 129, 0.12)';
        ctx.lineWidth = 1;

        // Rounded rect for slip
        const r = 4;
        ctx.beginPath();
        ctx.roundRect(drawX, drawY, rec.width, 24, r);
        ctx.fill();
        ctx.stroke();

        // Left color pip
        ctx.fillStyle = rec.type === 'invoice'
          ? 'rgba(56, 189, 248, 0.6)'
          : rec.type === 'settlement'
          ? 'rgba(99, 102, 241, 0.6)'
          : 'rgba(16, 185, 129, 0.6)';
        ctx.beginPath();
        ctx.arc(drawX + 8, drawY + 12, 2.5, 0, Math.PI * 2);
        ctx.fill();

        // Reference Code
        ctx.font = '8px "JetBrains Mono", monospace';
        ctx.fillStyle = 'rgba(203, 213, 225, 0.4)';
        ctx.fillText(rec.ref, drawX + 16, drawY + 11);

        // Amount & Category
        ctx.font = '8px "JetBrains Mono", monospace';
        ctx.fillStyle = 'rgba(148, 163, 184, 0.35)';
        ctx.fillText(rec.amount, drawX + 16, drawY + 20);

        // Right status tag
        ctx.font = '7px "JetBrains Mono", monospace';
        ctx.fillStyle = rec.status === 'MATCHED' || rec.status === 'EXACT' || rec.status === 'VERIFIED'
          ? 'rgba(52, 211, 153, 0.4)'
          : rec.status === 'DELAYED'
          ? 'rgba(251, 191, 36, 0.4)'
          : 'rgba(248, 113, 113, 0.4)';
        ctx.fillText(rec.status, drawX + rec.width - 34, drawY + 15);
      });

      // -----------------------------------------------------------------------
      // LAYER 3: RECONCILIATION CONNECTION NETWORK (Z = 0.85)
      // Parallax rate: 10px mouse, 0.25x scroll
      // Shows: Invoices + Settlements + Bank -> Central Match Node -> Terminal Status
      // -----------------------------------------------------------------------
      const l3ParallaxX = currentParallaxX * 24;
      const l3ParallaxY = currentParallaxY * 24 - (currentScrollY * 0.2);

      networkBranches.forEach(branch => {
        if (!prefersReducedMotion) {
          branch.progress = (branch.progress + branch.speed * speedMultiplier) % 1;
        }

        const ix = branch.invX + l3ParallaxX;
        const iy = branch.invY + l3ParallaxY;
        const sx = branch.setX + l3ParallaxX;
        const sy = branch.setY + l3ParallaxY;
        const bx = branch.bnkX + l3ParallaxX;
        const by = branch.bnkY + l3ParallaxY;
        const mx = branch.matchX + l3ParallaxX;
        const my = branch.matchY + l3ParallaxY;
        const dx = branch.destX + l3ParallaxX;
        const dy = branch.destY + l3ParallaxY;

        // 3-way converging feeder lines to Match Node
        ctx.lineWidth = 1;

        // Invoice feed line
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.12)';
        ctx.beginPath();
        ctx.moveTo(ix, iy);
        ctx.quadraticCurveTo((ix + mx) * 0.5, iy, mx, my);
        ctx.stroke();

        // Settlement feed line
        ctx.strokeStyle = 'rgba(99, 102, 241, 0.12)';
        ctx.beginPath();
        ctx.moveTo(sx, sy);
        ctx.quadraticCurveTo((sx + mx) * 0.5, sy, mx, my);
        ctx.stroke();

        // Bank feed line
        ctx.strokeStyle = 'rgba(16, 185, 129, 0.12)';
        ctx.beginPath();
        ctx.moveTo(bx, by);
        ctx.quadraticCurveTo((bx + mx) * 0.5, by, mx, my);
        ctx.stroke();

        // Match Node Core (Circle in center)
        ctx.beginPath();
        ctx.arc(mx, my, 4, 0, Math.PI * 2);
        ctx.fillStyle = branch.type === 'verified'
          ? 'rgba(6, 182, 212, 0.35)'
          : branch.type === 'review'
          ? 'rgba(245, 158, 11, 0.35)'
          : 'rgba(239, 68, 68, 0.35)';
        ctx.fill();

        ctx.strokeStyle = branch.type === 'verified'
          ? 'rgba(6, 182, 212, 0.5)'
          : branch.type === 'review'
          ? 'rgba(245, 158, 11, 0.5)'
          : 'rgba(239, 68, 68, 0.5)';
        ctx.lineWidth = 1;
        ctx.stroke();

        // Outcome Path from Match Node -> Destination
        ctx.beginPath();
        ctx.moveTo(mx, my);
        ctx.quadraticCurveTo((mx + dx) * 0.5, (my + dy) * 0.5 - 15, dx, dy);

        if (branch.type === 'verified') {
          ctx.strokeStyle = 'rgba(34, 211, 238, 0.18)';
        } else if (branch.type === 'review') {
          ctx.strokeStyle = 'rgba(251, 191, 36, 0.16)';
        } else {
          ctx.strokeStyle = 'rgba(248, 113, 113, 0.16)';
          ctx.setLineDash([3, 4]);
        }
        ctx.lineWidth = 1.25;
        ctx.stroke();
        ctx.setLineDash([]);

        // Flowing verification data pulse along outcome path
        const t = branch.progress;
        const cx = (mx + dx) * 0.5;
        const cy = (my + dy) * 0.5 - 15;
        const px = (1 - t) * (1 - t) * mx + 2 * (1 - t) * t * cx + t * t * dx;
        const py = (1 - t) * (1 - t) * my + 2 * (1 - t) * t * cy + t * t * dy;

        // Pulse dot
        ctx.beginPath();
        ctx.arc(px, py, branch.pulseSize, 0, Math.PI * 2);
        ctx.fillStyle = branch.type === 'verified'
          ? 'rgba(34, 211, 238, 0.8)'
          : branch.type === 'review'
          ? 'rgba(251, 191, 36, 0.8)'
          : 'rgba(248, 113, 113, 0.8)';
        ctx.fill();

        // Destination Terminal Node with mini label
        ctx.beginPath();
        ctx.arc(dx, dy, 3, 0, Math.PI * 2);
        ctx.fillStyle = branch.type === 'verified'
          ? 'rgba(16, 185, 129, 0.6)'
          : branch.type === 'review'
          ? 'rgba(245, 158, 11, 0.6)'
          : 'rgba(239, 68, 68, 0.6)';
        ctx.fill();

        ctx.font = '7.5px "JetBrains Mono", monospace';
        ctx.fillStyle = branch.type === 'verified'
          ? 'rgba(52, 211, 153, 0.35)'
          : branch.type === 'review'
          ? 'rgba(251, 191, 36, 0.35)'
          : 'rgba(248, 113, 113, 0.35)';
        ctx.fillText(branch.label, dx + 6, dy + 2.5);
      });

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('scroll', handleScroll);
      window.removeEventListener('resize', handleResize);
    };
  }, [currentRun?.run_id, isRunning, hasSelectedResult]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0 overflow-hidden"
      aria-hidden="true"
    />
  );
}
