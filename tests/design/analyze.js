async (payload) => {
  const load = (src) => new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('image decode failed'));
    img.src = src;
  });
  const pixels = async (src) => {
    const img = await load(src);
    const canvas = document.createElement('canvas');
    canvas.width = img.width;
    canvas.height = img.height;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(img, 0, 0);
    return { w: img.width, h: img.height, data: ctx.getImageData(0, 0, img.width, img.height).data };
  };

  const toLab = (r, g, b) => {
    const lin = (v) => { const c = v / 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
    const R = lin(r), G = lin(g), B = lin(b);
    const X = (R * 0.4124 + G * 0.3576 + B * 0.1805) / 0.95047;
    const Y = (R * 0.2126 + G * 0.7152 + B * 0.0722);
    const Z = (R * 0.0193 + G * 0.1192 + B * 0.9505) / 1.08883;
    const f = (t) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
    const fx = f(X), fy = f(Y), fz = f(Z);
    return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
  };
  const lum = (r, g, b) => {
    const lin = (v) => { const c = v / 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  };

  const card = await pixels(payload.card);
  const blank = await pixels(payload.blank);
  const hidden = await pixels(payload.hidden);
  if (card.w !== blank.w || card.h !== blank.h) {
    throw new Error('卡片图与空白舞台尺寸不一致: ' + card.w + 'x' + card.h + ' vs ' + blank.w + 'x' + blank.h);
  }

  const { w, h } = card;
  const A = card.data, B = blank.data;
  // 左右边带按 sideTolerance 向内收: 只排除跨平台字体 bearing 造成的贴边
  // 几像素墨迹, 上下边带不动, 真正的越界图形仍然会被逐像素抓到。
  const side = payload.safeSide - (payload.sideTolerance || 0);
  const bands = [
    { name: 'top', x0: 0, x1: w, y0: 0, y1: payload.safeTop },
    { name: 'bottom', x0: 0, x1: w, y0: h - payload.safeBottom, y1: h },
    { name: 'left', x0: 0, x1: side, y0: 0, y1: h },
    { name: 'right', x0: w - side, x1: w, y0: 0, y1: h },
  ];
  let worst = { de: 0, x: 0, y: 0, band: 'none' };
  for (const band of bands) {
    for (let y = band.y0; y < band.y1; y++) {
      for (let x = band.x0; x < band.x1; x++) {
        const i = (y * w + x) * 4;
        // 绝大多数像素两张图逐字节相同, 先做便宜的比较
        if (A[i] === B[i] && A[i + 1] === B[i + 1] && A[i + 2] === B[i + 2]) continue;
        const la = toLab(A[i], A[i + 1], A[i + 2]);
        const lb = toLab(B[i], B[i + 1], B[i + 2]);
        const de = Math.sqrt((la[0] - lb[0]) ** 2 + (la[1] - lb[1]) ** 2 + (la[2] - lb[2]) ** 2);
        if (de > worst.de) worst = { de, x, y, band: band.name };
      }
    }
  }

  const H = hidden.data;
  const slots = payload.boxes.map((box) => {
    const x0 = Math.max(0, Math.round(box.x + box.w * 0.1));
    const x1 = Math.min(hidden.w, Math.round(box.x + box.w * 0.9));
    const y0 = Math.max(0, Math.round(box.y + box.h * 0.2));
    const y1 = Math.min(hidden.h, Math.round(box.y + box.h * 0.8));
    let best = { lum: -1, rgb: [0, 0, 0] };
    for (let y = y0; y < y1; y += 2) {
      for (let x = x0; x < x1; x += 2) {
        const i = (y * hidden.w + x) * 4;
        const value = lum(H[i], H[i + 1], H[i + 2]);
        if (value > best.lum) best = { lum: value, rgb: [H[i], H[i + 1], H[i + 2]] };
      }
    }
    return { slot: box.slot, bg: best.rgb, bgLum: best.lum };
  });

  return { size: { w, h }, worst, slots };
}
