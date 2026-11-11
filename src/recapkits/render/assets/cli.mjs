import { readFileSync, writeFileSync } from "node:fs";
class RenderError extends Error {
  constructor(message) {
    super(message);
    this.name = "RenderError";
  }
}
var n, l$1, u$2, t, w$1 = [];
function k$1(l2, u2, t2) {
  var i2, r, o2, e = {};
  for (o2 in u2) "key" == o2 ? i2 = u2[o2] : "ref" == o2 ? r = u2[o2] : e[o2] = u2[o2];
  if (arguments.length > 2 && (e.children = arguments.length > 3 ? n.call(arguments, 2) : t2), "function" == typeof l2 && null != l2.defaultProps) for (o2 in l2.defaultProps) void 0 === e[o2] && (e[o2] = l2.defaultProps[o2]);
  return x$1(l2, e, i2, r, null);
}
function x$1(n2, t2, i2, r, o2) {
  var e = { type: n2, props: t2, key: i2, ref: r, __k: null, __: null, __b: 0, __e: null, __c: null, constructor: void 0, __v: null == o2 ? ++u$2 : o2, __i: -1, __u: 0 };
  return null != l$1.vnode && l$1.vnode(e), e;
}
function S(n2) {
  return n2.children;
}
n = w$1.slice, l$1 = { __e: function(n2, l2, u2, t2) {
  for (var i2, r, o2; l2 = l2.__; ) if ((i2 = l2.__c) && !i2.__) try {
    if ((r = i2.constructor) && null != r.getDerivedStateFromError && (i2.setState(r.getDerivedStateFromError(n2)), o2 = i2.__d), null != i2.componentDidCatch && (i2.componentDidCatch(n2, t2 || {}), o2 = i2.__d), o2) return i2.__E = i2;
  } catch (l3) {
    n2 = l3;
  }
  throw n2;
} }, u$2 = 0, t = function(n2) {
  return null != n2 && void 0 === n2.constructor;
}, "function" == typeof Promise ? Promise.prototype.then.bind(Promise.resolve()) : setTimeout, Math.random().toString(8);
var f$1 = 0;
function u$1(e, t2, n2, o2, i2, u2) {
  t2 || (t2 = {});
  var a2, c2, p2 = t2;
  if ("ref" in p2) for (c2 in p2 = {}, t2) "ref" == c2 ? a2 = t2[c2] : p2[c2] = t2[c2];
  var l2 = { type: e, props: p2, key: n2, ref: a2, __k: null, __: null, __b: 0, __e: null, __c: null, constructor: void 0, __v: --f$1, __i: -1, __u: 0, __source: i2, __self: u2 };
  if ("function" == typeof e && (a2 = e.defaultProps)) for (c2 in a2) void 0 === p2[c2] && (p2[c2] = a2[c2]);
  return l$1.vnode && l$1.vnode(l2), l2;
}
var o = "__s", i = "__c", a = "__k", u = "__d", c = "__s", f = /[\s\n\\/='"\0<>]/, s = /^(xlink|xmlns|xml)([A-Z])/, l = /^(?:accessK|auto[A-Z]|cell|ch|col|cont|cross|dateT|encT|form[A-Z]|frame|hrefL|inputM|maxL|minL|noV|playsI|popoverT|readO|rowS|src[A-Z]|tabI|useM|item[A-Z])/, p = /^ac|^ali|arabic|basel|cap|clipPath$|clipRule$|color|dominant|enable|fill|flood|font|glyph[^R]|horiz|image|letter|lighting|marker[^WUH]|overline|panose|pointe|paint|rendering|shape|stop|strikethrough|stroke|text[^L]|transform|underline|unicode|units|^v[^i]|^w|^xH/, h = /* @__PURE__ */ new Set(["draggable", "spellcheck"]);
function d(e) {
  void 0 !== e.__g ? e.__g |= 8 : e[u] = true;
}
function v(e) {
  void 0 !== e.__g ? e.__g &= -9 : e[u] = false;
}
function m(e) {
  return void 0 !== e.__g ? !!(8 & e.__g) : true === e[u];
}
var y = /["&<]/;
function _(e) {
  if (0 === e.length || false === y.test(e)) return e;
  for (var t2 = 0, n2 = 0, r = "", o2 = ""; n2 < e.length; n2++) {
    switch (e.charCodeAt(n2)) {
      case 34:
        o2 = "&quot;";
        break;
      case 38:
        o2 = "&amp;";
        break;
      case 60:
        o2 = "&lt;";
        break;
      default:
        continue;
    }
    n2 !== t2 && (r += e.slice(t2, n2)), r += o2, t2 = n2 + 1;
  }
  return n2 !== t2 && (r += e.slice(t2, n2)), r;
}
var g = {}, k = /* @__PURE__ */ new Set(["animation-iteration-count", "border-image-outset", "border-image-slice", "border-image-width", "box-flex", "box-flex-group", "box-ordinal-group", "column-count", "fill-opacity", "flex", "flex-grow", "flex-negative", "flex-order", "flex-positive", "flex-shrink", "flood-opacity", "font-weight", "grid-column", "grid-row", "line-clamp", "line-height", "opacity", "order", "orphans", "stop-opacity", "stroke-dasharray", "stroke-dashoffset", "stroke-miterlimit", "stroke-opacity", "stroke-width", "tab-size", "widows", "z-index", "zoom"]), b = /[A-Z]/g;
function x(e) {
  var t2 = "";
  for (var n2 in e) {
    var r = e[n2];
    if (null != r && "" !== r) {
      var o2 = "-" == n2[0] ? n2 : g[n2] || (g[n2] = n2.replace(b, "-$&").toLowerCase()), i2 = ";";
      "number" != typeof r || o2.startsWith("--") || k.has(o2) || (i2 = "px;"), t2 = t2 + o2 + ":" + r + i2;
    }
  }
  return t2 || void 0;
}
function w() {
  this.__d = true;
}
function H(e, t2) {
  return { __v: e, context: t2, props: e.props, setState: w, forceUpdate: w, __d: true, __h: new Array(0) };
}
var T = {}, j = [], P = Array.isArray, $ = Object.assign, U = "", Z = "<!--$s-->", F = "<!--/$s-->";
function M(e) {
  return "string" == typeof e ? Z + e + F : P(e) ? (e.unshift(Z), e.push(F), e) : e && "function" == typeof e.then ? e.then(M) : Z + e + F;
}
function W() {
  return { beforeDiff: l$1.__b, afterDiff: l$1.diffed, renderHook: l$1.__r, unmountHook: l$1.unmount, rootHook: l$1.__, commitHook: l$1.__c, catchError: l$1.__e, errorBoundaries: l$1.errorBoundaries };
}
function B(e) {
  var t2 = l$1[o];
  l$1[o] = true;
  try {
    return e();
  } finally {
    l$1[o] = t2;
  }
}
function z(n2, r, o2) {
  var i2 = W();
  try {
    var u2 = B(function() {
      var u3, c2 = k$1(S, null);
      return c2[a] = [n2], i2.rootHook && i2.rootHook(n2, ((u3 = {})[a] = c2, u3.nodeType = 1, u3)), q(n2, r || T, false, void 0, c2, false, o2, i2);
    });
    return P(u2) ? u2.join(U) : u2;
  } catch (e) {
    if (e.then) throw new Error('Use "renderToStringAsync" for suspenseful rendering.');
    throw e;
  } finally {
    i2.commitHook && B(function() {
      return i2.commitHook(n2, j);
    }), j.length = 0;
  }
}
function N(e, t2, n2) {
  var r, o2 = e.type, a2 = true;
  return e[i] ? (a2 = false, (r = e[i]).state = r[c]) : r = new o2(e.props, t2), e[i] = r, r.__v = e, r.props = e.props, r.context = t2, d(r), null == r.state && (r.state = T), null == r[c] && (r[c] = r.state), o2.getDerivedStateFromProps ? r.state = $({}, r.state, o2.getDerivedStateFromProps(r.props, r.state)) : a2 && r.componentWillMount ? (r.componentWillMount(), r.state = r[c] !== r.state ? r[c] : r.state) : !a2 && r.componentWillUpdate && r.componentWillUpdate(), n2.renderHook && n2.renderHook(e), r.render(r.props, r.state, t2);
}
function q(e, n2, o2, u2, y2, g2, k2, b2) {
  if (null == e || true === e || false === e || e === U) return U;
  var w2 = typeof e;
  if ("object" != w2) return "function" == w2 ? U : "string" == w2 ? _(e) : e + U;
  if (P(e)) {
    var C, D = U;
    y2[a] = e;
    for (var A = e.length, S$1 = 0; S$1 < A; S$1++) {
      var E = e[S$1];
      if (null != E && "boolean" != typeof E) {
        var L, j2 = q(E, n2, o2, u2, y2, g2, k2, b2);
        "string" == typeof j2 ? D += j2 : (C || (C = new Array(A)), D && C.push(D), D = U, P(j2) ? (L = C).push.apply(L, j2) : C.push(j2));
      }
    }
    return C ? (D && C.push(D), C) : D;
  }
  if (!t(e)) return U;
  e.__ = y2, b2.beforeDiff && b2.beforeDiff(e);
  var Z2 = e.type, F2 = e.props;
  if ("function" == typeof Z2) {
    var W2, z2, O, R = n2;
    if (Z2 === S) {
      if ("tpl" in F2) {
        for (var K, G = U, J = 0; J < F2.tpl.length; J++) if (G += F2.tpl[J], F2.exprs && J < F2.exprs.length) {
          var Q = F2.exprs[J];
          if (null == Q) continue;
          if ("object" == typeof Q && (t(Q) || P(Q))) {
            var X, Y = q(Q, n2, o2, u2, e, g2, k2, b2);
            "string" == typeof Y ? G += Y : (K || (K = []), G && K.push(G), G = U, P(Y) ? (X = K).push.apply(X, Y) : K.push(Y));
          } else G += Q;
        }
        return K ? (G && K.push(G), K) : G;
      }
      if ("UNSTABLE_comment" in F2) return "<!--" + _(F2.UNSTABLE_comment) + "-->";
      z2 = F2.children;
    } else {
      if (null != (W2 = Z2.contextType)) {
        var ee = n2[W2.__c];
        R = ee ? ee.props.value : W2.__;
      }
      var te = Z2.prototype && "function" == typeof Z2.prototype.render;
      if (te) z2 = /**#__NOINLINE__**/
      N(e, R, b2), O = e[i];
      else {
        e[i] = O = /**#__NOINLINE__**/
        H(e, R);
        for (var ne = 0; m(O) && ne++ < 25; ) {
          v(O), b2.renderHook && b2.renderHook(e);
          try {
            z2 = Z2.call(O, F2, R);
          } catch (t2) {
            throw t2;
          }
        }
        d(O);
      }
      if (null != O.getChildContext && (n2 = $({}, n2, O.getChildContext())), te && b2.errorBoundaries && (Z2.getDerivedStateFromError || O.componentDidCatch)) {
        z2 = null != z2 && z2.type === S && null == z2.key && null == z2.props.tpl ? z2.props.children : z2;
        try {
          return q(z2, n2, o2, u2, e, g2, false, b2);
        } catch (r) {
          return Z2.getDerivedStateFromError && (O[c] = Z2.getDerivedStateFromError(r)), O.componentDidCatch && O.componentDidCatch(r, T), m(O) ? (z2 = N(e, n2, b2), null != (O = e[i]).getChildContext && (n2 = $({}, n2, O.getChildContext())), q(z2 = null != z2 && z2.type === S && null == z2.key && null == z2.props.tpl ? z2.props.children : z2, n2, o2, u2, e, g2, k2, b2)) : U;
        } finally {
          b2.afterDiff && b2.afterDiff(e), b2.unmountHook && b2.unmountHook(e);
        }
      }
    }
    z2 = null != z2 && z2.type === S && null == z2.key && null == z2.props.tpl ? z2.props.children : z2;
    try {
      var re = q(z2, n2, o2, u2, e, g2, k2, b2);
      return b2.afterDiff && b2.afterDiff(e), b2.unmountHook && b2.unmountHook(e), e._suspended ? M(re) : re;
    } catch (t2) {
      if (k2 && k2.onError) {
        var oe = (function t3(r) {
          return k2.onError(r, e, function(e2, r2) {
            try {
              return B(function() {
                return q(e2, n2, o2, u2, r2, g2, k2, b2);
              });
            } catch (e3) {
              return t3(e3);
            }
          });
        })(t2);
        return void 0 !== oe ? oe : (b2.catchError && b2.catchError(t2, e), U);
      }
      throw t2;
    }
  }
  var ie, ae = "<" + Z2, ue = U;
  for (var ce in F2) {
    var fe = F2[ce];
    if ("function" != typeof (fe = V(fe) ? fe.value : fe) || "class" === ce || "className" === ce) {
      switch (ce) {
        case "children":
          ie = fe;
          continue;
        case "key":
        case "ref":
        case "__self":
        case "__source":
          continue;
        case "htmlFor":
          if ("for" in F2) continue;
          ce = "for";
          break;
        case "className":
          if ("class" in F2) continue;
          ce = "class";
          break;
        case "defaultChecked":
          ce = "checked";
          break;
        case "defaultSelected":
          ce = "selected";
          break;
        case "defaultValue":
        case "value":
          switch (ce = "value", Z2) {
            case "textarea":
              ie = fe;
              continue;
            case "select":
              u2 = fe;
              continue;
            case "option":
              u2 != fe || "selected" in F2 || (ae += " selected");
          }
          break;
        case "dangerouslySetInnerHTML":
          ue = fe && fe.__html;
          continue;
        case "style":
          "object" == typeof fe && (fe = x(fe));
          break;
        case "acceptCharset":
          ce = "accept-charset";
          break;
        case "httpEquiv":
          ce = "http-equiv";
          break;
        default:
          if (f.test(ce)) continue;
          s.test(ce) ? ce = ce.replace(s, "$1:$2").toLowerCase() : "-" !== ce[4] && !h.has(ce) || null == fe ? o2 ? p.test(ce) && (ce = "panose1" === ce ? "panose-1" : ce.replace(/([A-Z])/g, "-$1").toLowerCase()) : l.test(ce) && (ce = ce.toLowerCase()) : fe += U;
      }
      null != fe && false !== fe && (ae = true === fe || fe === U ? ae + " " + ce : ae + " " + ce + '="' + _(fe + U) + '"');
    }
  }
  if (f.test(Z2)) throw new Error(Z2 + " is not a valid HTML tag name in " + ae + ">");
  if (ue || ("string" == typeof ie ? ue = _(ie) : null != ie && false !== ie && true !== ie && (ue = q(ie, n2, "svg" === Z2 || "foreignObject" !== Z2 && o2, u2, e, g2, k2, b2))), b2.afterDiff && b2.afterDiff(e), b2.unmountHook && b2.unmountHook(e), !ue && I.has(Z2)) return ae + "/>";
  var se = "</" + Z2 + ">", le = ae + ">";
  return P(ue) ? [le].concat(ue, [se]) : "string" != typeof ue ? [le, ue, se] : le + ue + se;
}
var I = /* @__PURE__ */ new Set(["area", "base", "br", "col", "command", "embed", "hr", "img", "input", "keygen", "link", "meta", "param", "source", "track", "wbr"]);
function V(e) {
  return null !== e && "object" == typeof e && "function" == typeof e.peek && "value" in e;
}
const baseCss = '/* 重置、舞台几何与卡片版式。\r\n *\r\n * 每张卡一屏: 竖向滚动 + scroll-snap。舞台尺寸由内联变量给出\r\n * (--stage-w / --stage-h, 单位 px), 缩放由 main.ts 的 10 行脚本按视口算,\r\n * 计算公式是 min(视口宽 / 舞台宽, 视口高 / 舞台高), 保证任何比例下都不裁切。\r\n */\r\n\r\n*,\r\n*::before,\r\n*::after {\r\n  box-sizing: border-box;\r\n}\r\n\r\nhtml,\r\nbody {\r\n  margin: 0;\r\n  padding: 0;\r\n}\r\n\r\nbody {\r\n  background: #05050a;\r\n  font-family: var(--font-sans);\r\n  -webkit-font-smoothing: antialiased;\r\n  text-rendering: optimizeLegibility;\r\n}\r\n\r\n.deck {\r\n  /* 100dvh 优先: 手机浏览器地址栏收起时 100vh 会多出一截, 导致一屏放不下一张卡。 */\r\n  height: 100vh;\r\n  height: 100dvh;\r\n  overflow-x: hidden;\r\n  overflow-y: scroll;\r\n  scroll-snap-type: y mandatory;\r\n  overscroll-behavior-y: contain;\r\n}\r\n\r\n.slide {\r\n  position: relative;\r\n  height: 100vh;\r\n  height: 100dvh;\r\n  overflow: hidden;\r\n  scroll-snap-align: start;\r\n  scroll-snap-stop: always;\r\n}\r\n\r\n/* 舞台用绝对定位 + 位移居中, 而不是 flex/grid 居中: 1080px 的子元素会把\r\n * auto 轨道撑到 1080, 于是"居中"其实是在一条 1080 宽的轨道里居中, 结果贴左溢出。\r\n * 绝对定位让子元素不参与父级尺寸计算, 任何视口下都真的居中。 */\r\n.stage {\r\n  position: absolute;\r\n  left: 50%;\r\n  top: 50%;\r\n  flex: none;\r\n  width: calc(var(--stage-w) * 1px);\r\n  height: calc(var(--stage-h) * 1px);\r\n  transform: translate(-50%, -50%) scale(var(--stage-scale, 0.3));\r\n  transform-origin: center center;\r\n  overflow: hidden;\r\n  isolation: isolate;\r\n  background-color: var(--skin-bg);\r\n  background-image: var(--skin-bg-image);\r\n  color: var(--skin-ink);\r\n  font-family: var(--font-sans);\r\n  font-kerning: normal;\r\n}\r\n\r\n/* 卡片: 所有卡片共享安全区与左右外边距, 只换内部排布。 */\r\n.card {\r\n  position: absolute;\r\n  inset: 0;\r\n  display: flex;\r\n  flex-direction: column;\r\n  padding: var(--safe-top) var(--margin) var(--safe-bottom);\r\n}\r\n\r\n.measure {\r\n  font-variant-numeric: tabular-nums;\r\n  letter-spacing: var(--track-tight);\r\n}\r\n\r\n/* 中文按字符断行, 不按空格断行; line-break: strict 让标点不落在行首。 */\r\n.copy {\r\n  margin: 0;\r\n  word-break: break-word;\r\n  overflow-wrap: anywhere;\r\n  line-break: strict;\r\n  text-wrap: pretty;\r\n}\r\n\r\n/* ---------- cover ---------- */\r\n\r\n.cover__kicker {\r\n  margin: 0;\r\n  font-size: var(--fs-caption);\r\n  line-height: 1.2;\r\n  letter-spacing: 0.16em;\r\n  color: var(--skin-accent);\r\n}\r\n\r\n.cover__year {\r\n  margin: 0;\r\n  margin-top: 104px;\r\n  font-size: var(--fs-display);\r\n  line-height: 0.84;\r\n  font-weight: 700;\r\n  color: var(--skin-ink);\r\n}\r\n\r\n.cover__sub {\r\n  margin: 56px 0 0;\r\n  font-size: var(--fs-lead);\r\n  line-height: 1.24;\r\n  color: var(--skin-muted);\r\n}\r\n\r\n.cover__rule {\r\n  margin: auto 0 0;\r\n  height: 2px;\r\n  width: 168px;\r\n  background: var(--skin-accent);\r\n}\r\n\r\n/* ---------- big-number ---------- */\r\n\r\n.big-number {\r\n  justify-content: flex-end;\r\n}\r\n\r\n.big-number__kicker {\r\n  position: absolute;\r\n  top: var(--safe-top);\r\n  left: var(--margin);\r\n  margin: 0;\r\n  font-size: var(--fs-micro);\r\n  line-height: 1.2;\r\n  letter-spacing: 0.18em;\r\n  color: var(--skin-faint);\r\n}\r\n\r\n.big-number__sub {\r\n  margin: 0 0 24px;\r\n  font-size: var(--fs-body);\r\n  line-height: 1.36;\r\n  color: var(--skin-muted);\r\n}\r\n\r\n.big-number__headline {\r\n  margin: 0 0 8px;\r\n  font-size: var(--fs-h2);\r\n  line-height: 1.04;\r\n  font-weight: 600;\r\n  color: var(--skin-ink);\r\n}\r\n\r\n.big-number__value {\r\n  /* line-height 0.9 + 0.12em 下移补偿: 行盒底落在安全区下沿时, CJK 字形仍会\r\n   * 向下溢出约 39px (实测 1080x1920)。这里把行盒上提 0.12em, 让字形的视觉底边\r\n   * 正好压在安全区下沿。字体确定性推迟到阶段 6, 届时随包字体落地后重测这一个值。 */\r\n  margin: 0 0 0.12em;\r\n  font-size: var(--fs-display);\r\n  line-height: 0.9;\r\n  font-weight: 700;\r\n  color: var(--skin-ink);\r\n}\r\n';
const WIDE_RANGES = [
  [4352, 4447],
  [11904, 12350],
  [12353, 13311],
  [13312, 19903],
  [19968, 40959],
  [40960, 42191],
  [44032, 55203],
  [63744, 64255],
  [65072, 65135],
  [65280, 65376],
  [65504, 65510],
  [127744, 128591],
  [131072, 262141]
];
const LATIN_RATIO = 0.55;
const SPACE_RATIO = 0.28;
function isWide(codePoint) {
  return WIDE_RANGES.some(([lo, hi]) => codePoint >= lo && codePoint <= hi);
}
function charWidth(char, size) {
  const codePoint = char.codePointAt(0) ?? 0;
  if (char === " " || char === " ") {
    return size * SPACE_RATIO;
  }
  return isWide(codePoint) ? size : size * LATIN_RATIO;
}
function measure(text, size) {
  let width = 0;
  for (const char of text) {
    width += charWidth(char, size);
  }
  return width;
}
function countLines(text, maxWidth, size) {
  let lines = 1;
  let used = 0;
  for (const token of tokenize(text)) {
    if (token === "\n") {
      lines += 1;
      used = 0;
      continue;
    }
    const width = measure(token, size);
    if (/^\s+$/.test(token)) {
      used = width + used > maxWidth ? used : used + width;
      continue;
    }
    if (used > 0 && used + width > maxWidth) {
      lines += 1;
      used = width;
      continue;
    }
    used += width;
  }
  return lines;
}
function tokenize(text) {
  const tokens = [];
  let buffer = "";
  for (const char of text) {
    if (/[0-9A-Za-z]/u.test(char)) {
      buffer += char;
      continue;
    }
    if (buffer) {
      tokens.push(buffer);
      buffer = "";
    }
    tokens.push(char);
  }
  if (buffer) {
    tokens.push(buffer);
  }
  return tokens;
}
const CONTENT_WIDTH = 1080 - 2 * 72;
const YEAR_SIZE = 320;
function Cover({ card }) {
  const year = card.copy.headline ?? "";
  const width = measure(year, YEAR_SIZE);
  if (year && width > CONTENT_WIDTH) {
    throw new RenderError(
      `卡片 ${card.id} 的 cover.headline 在 ${YEAR_SIZE}px 下宽 ${Math.round(width)}px, 超过 ${CONTENT_WIDTH}px; 缩短文案, 或换用 big-number`
    );
  }
  return /* @__PURE__ */ u$1("div", { class: "card cover", children: [
    card.copy.kicker ? /* @__PURE__ */ u$1("p", { class: "copy cover__kicker", children: card.copy.kicker }) : null,
    /* @__PURE__ */ u$1("h1", { class: "copy cover__year measure", children: year }),
    card.copy.sub ? /* @__PURE__ */ u$1("p", { class: "copy cover__sub", children: card.copy.sub }) : null,
    /* @__PURE__ */ u$1("div", { class: "cover__rule", "aria-hidden": "true" })
  ] });
}
const SUB_SIZE = 56;
const HEADLINE_SIZE = 140;
function BigNumber({ card }) {
  const headline = card.copy.headline ?? "";
  const sub = card.copy.sub ?? "";
  const number = card.number ?? "";
  const hasNumber = number.length > 0;
  if (headline) {
    const lines = countLines(headline, CONTENT_WIDTH, HEADLINE_SIZE);
    if (lines > 1) {
      throw new RenderError(
        `卡片 ${card.id} 的 big-number.headline 在 ${HEADLINE_SIZE}px 下占 ${lines} 行, 只允许 1 行; 缩短到 ${Math.floor(CONTENT_WIDTH / HEADLINE_SIZE)} 个汉字以内, 或移进 sub`
      );
    }
  }
  if (sub) {
    const lines = countLines(sub, CONTENT_WIDTH, SUB_SIZE);
    if (lines > 2) {
      throw new RenderError(
        `卡片 ${card.id} 的 big-number.sub 在 ${SUB_SIZE}px 下占 ${lines} 行, 最多 2 行; 缩短文案, 或把细节挪到另一张卡`
      );
    }
  }
  if (!hasNumber && !headline) {
    throw new RenderError(`卡片 ${card.id} 的 big-number 既没有 number 也没有 headline, 无法出图`);
  }
  return /* @__PURE__ */ u$1("div", { class: "card big-number", children: [
    card.copy.kicker ? /* @__PURE__ */ u$1("p", { class: "copy big-number__kicker", children: card.copy.kicker }) : null,
    sub ? /* @__PURE__ */ u$1("p", { class: "copy big-number__sub", children: sub }) : null,
    hasNumber && headline ? /* @__PURE__ */ u$1("p", { class: "copy big-number__headline", children: headline }) : null,
    /* @__PURE__ */ u$1("p", { class: "copy big-number__value measure", children: hasNumber ? number : headline })
  ] });
}
const ASPECTS = {
  "9:16": { width: 1080, height: 1920 },
  "4:5": { width: 1080, height: 1350 }
};
const CARD_COMPONENTS = {
  cover: Cover,
  "big-number": BigNumber
};
function Card({ card }) {
  const Component = CARD_COMPONENTS[card.type];
  if (!Component) {
    throw new RenderError(
      `卡片 ${card.id} 的类型 ${card.type} 尚未实现; 阶段 5 只支持 cover 与 big-number`
    );
  }
  return /* @__PURE__ */ u$1(Component, { card });
}
function Stage({ card, aspect }) {
  const size = ASPECTS[aspect];
  return /* @__PURE__ */ u$1("section", { class: "slide", children: /* @__PURE__ */ u$1(
    "div",
    {
      class: "stage",
      style: `--stage-w:${size.width};--stage-h:${size.height}`,
      "data-card": card.id,
      children: /* @__PURE__ */ u$1(Card, { card })
    }
  ) });
}
function Deck({ story, aspect }) {
  return /* @__PURE__ */ u$1("main", { class: "deck", children: story.cards.map((card) => /* @__PURE__ */ u$1(Stage, { card, aspect }, card.id)) });
}
const tokensCss = '/* 设计 token。\r\n *\r\n * 布局一律用绝对像素: 舞台固定 1080x1920 (或 1080x1350), 缩放只发生在 .stage 的\r\n * transform 上。这样 PNG/MP4 阶段的截图与浏览器里看到的是同一套几何, 不需要为\r\n * 两个目标各调一遍。\r\n *\r\n * 字体确定性推迟到 PNG/MP4 阶段 (阶段 6/7)。HTML 阶段用系统字体栈, 因为:\r\n * 1) 在浏览器里 CJK 字体本来就由系统提供, 随包字体只会让文件变大;\r\n * 2) CJK 子集化是件正经工作 (需要按实际文案裁剪字形), 在还没有像素输出的阶段\r\n *    为它付费没有回报。\r\n * 阶段 6 引入随包 WOFF2 时, 只替换下面的 --font-sans 与其 @font-face, 布局不用动。\r\n * 看到这里没有 @font-face 是**故意的**, 不是漏了。\r\n */\r\n\r\n:root {\r\n  --col: 56px; --gutter: 24px; --margin: 72px;\r\n  --safe-top: 240px; --safe-bottom: 240px;\r\n  --fs-display: 320px; --fs-h1: 220px; --fs-h2: 140px;\r\n  --fs-lead: 88px; --fs-body: 56px; --fs-caption: 40px; --fs-micro: 28px;\r\n  --track-tight: -0.025em;\r\n  --dur-fast: 160ms; --dur-mid: 400ms; --dur-slow: 700ms;\r\n  --ease-out: cubic-bezier(0.2, 0.7, 0.1, 1);\r\n\r\n  --font-sans: "Inter Tight", -apple-system, "Segoe UI", "PingFang SC",\r\n    "Microsoft YaHei", "Noto Sans SC", sans-serif;\r\n}\r\n\r\n/* 主题 neon: 暗底、饱和渐变、白色文字、单一强调色。文字不加投影。 */\r\n:root {\r\n  --skin-bg: #0b0b0f;\r\n  --skin-bg-image: radial-gradient(118% 78% at 82% -8%, rgba(198, 255, 61, 0.22), transparent 58%),\r\n    linear-gradient(158deg, #17171f 0%, #0b0b0f 52%, #06060a 100%);\r\n  --skin-ink: #ffffff;\r\n  --skin-muted: rgba(255, 255, 255, 0.6);\r\n  --skin-faint: rgba(255, 255, 255, 0.38);\r\n  --skin-accent: #c6ff3d;\r\n  --skin-rule: rgba(255, 255, 255, 0.14);\r\n}\r\n';
function assertBaked(story) {
  const seen = [];
  for (const card of story.cards) {
    const values = [
      card.copy.headline,
      card.copy.sub,
      card.copy.kicker,
      card.number
    ];
    for (const value of values) {
      if (typeof value === "string" && (value.includes("{{") || value.includes("}}"))) {
        seen.push(`卡片 ${card.id}: ${value}`);
      }
    }
  }
  if (seen.length > 0) {
    throw new RenderError(
      `收到未烘焙的占位符, 渲染器不做占位符解析; 先跑 story/bake.py。
  ${seen.join("\n  ")}`
    );
  }
}
function scaleScript(width, height) {
  return `<script>(function(){var W=${width},H=${height};function fit(){var s=Math.min(window.innerWidth/W,window.innerHeight/H);document.documentElement.style.setProperty("--stage-scale",String(s));}fit();window.addEventListener("resize",fit);})();<\/script>`;
}
function renderStory(story, options) {
  assertBaked(story);
  const size = ASPECTS[options.aspect];
  const body = z(/* @__PURE__ */ u$1(Deck, { story, aspect: options.aspect }));
  const title = `${story.meta.year} 年度回顾`;
  return [
    "<!DOCTYPE html>",
    `<html lang="zh-CN" data-theme="${escapeAttribute(options.theme)}">`,
    "<head>",
    '<meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
    `<title>${escapeText(title)}</title>`,
    scaleScript(size.width, size.height),
    `<style>${tokensCss}
${baseCss}</style>`,
    "</head>",
    "<body>",
    body,
    "</body>",
    "</html>",
    ""
  ].join("\n");
}
function escapeText(value) {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function escapeAttribute(value) {
  return escapeText(value).replace(/"/g, "&quot;");
}
const USAGE = "用法: node cli.mjs --story <baked.json> [--aspect 9:16|4:5] [--theme neon] [--out <file>]";
function parseArgs(argv) {
  const args = { story: "", aspect: "9:16", theme: "neon", out: null };
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    const value = argv[index + 1];
    switch (flag) {
      case "--story":
        args.story = value ?? "";
        index += 1;
        break;
      case "--aspect":
        if (value !== "9:16" && value !== "4:5") {
          throw new RenderError(`--aspect 只支持 9:16 或 4:5, 收到 ${value ?? "(空)"}`);
        }
        args.aspect = value;
        index += 1;
        break;
      case "--theme":
        args.theme = value ?? "neon";
        index += 1;
        break;
      case "--out":
        args.out = value ?? null;
        index += 1;
        break;
      default:
        throw new RenderError(`未知参数 ${flag}
${USAGE}`);
    }
  }
  if (!args.story) {
    throw new RenderError(USAGE);
  }
  return args;
}
function main(argv) {
  const args = parseArgs(argv);
  const story = JSON.parse(readFileSync(args.story, "utf8"));
  const html = renderStory(story, { aspect: args.aspect, theme: args.theme });
  if (args.out) {
    writeFileSync(args.out, html, "utf8");
  } else {
    process.stdout.write(html);
  }
  return 0;
}
try {
  process.exitCode = main(process.argv.slice(2));
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`${message}
`);
  process.exitCode = 1;
}
