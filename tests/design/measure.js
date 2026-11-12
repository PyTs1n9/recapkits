(el) => {
  const stage = el;
  const s = stage.getBoundingClientRect();
  const parse = (value) => {
    const nums = value.match(/[\d.]+/g).map(Number);
    return { rgb: nums.slice(0, 3), alpha: nums.length > 3 ? nums[3] : 1 };
  };
  const items = [];
  for (const node of stage.querySelectorAll('[data-fit]')) {
    const cs = getComputedStyle(node);
    const r = node.getBoundingClientRect();
    // 行数用 Range 的行盒去数: clientHeight / lineHeight 会被字形墨迹带偏
    // 行数要按"视觉行"数, 不能按 inline 盒的 top 数: 数值后面跟一个字号更小的
    // 单位 (137 + 次) 会产生两个 top, 但它们是同一行。
    const range = document.createRange();
    range.selectNodeContents(node);
    const rows = [];
    for (const rect of [...range.getClientRects()].sort((a, b) => a.top - b.top)) {
      const last = rows[rows.length - 1];
      if (last && rect.top < last.bottom - 1) {
        last.bottom = Math.max(last.bottom, rect.bottom);
      } else {
        rows.push({ top: rect.top, bottom: rect.bottom });
      }
    }
    const paint = parse(cs.color);
    items.push({
      slot: node.getAttribute('data-fit'),
      tag: node.tagName.toLowerCase(),
      x: r.left - s.left, y: r.top - s.top, w: r.width, h: r.height,
      scrollW: node.scrollWidth, clientW: node.clientWidth,
      lines: rows.length,
      color: paint.rgb, alpha: paint.alpha,
      size: parseFloat(cs.fontSize),
    });
  }
  const foot = stage.querySelector('.card__foot');
  return {
    slots: items,
    stage: { w: s.width, h: s.height },
    footTop: foot ? foot.getBoundingClientRect().top - s.top : null,
  };
}
