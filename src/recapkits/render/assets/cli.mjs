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
const SUB_SIZE$2 = 88;
function Cover({ card }) {
  const year = card.copy.headline ?? "";
  const width = measure(year, YEAR_SIZE);
  if (year && width > CONTENT_WIDTH) {
    throw new RenderError(
      `卡片 ${card.id} 的 cover.headline 在 ${YEAR_SIZE}px 下宽 ${Math.round(width)}px, 超过 ${CONTENT_WIDTH}px; 缩短文案, 或换用 big-number`
    );
  }
  const sub = card.copy.sub ?? "";
  if (sub && countLines(sub, CONTENT_WIDTH, SUB_SIZE$2) > 2) {
    throw new RenderError(
      `卡片 ${card.id} 的 cover.sub 在 ${SUB_SIZE$2}px 下超过 2 行; 缩短文案, 或挪进另一张卡`
    );
  }
  return /* @__PURE__ */ u$1("div", { class: "card cover", children: [
    /* @__PURE__ */ u$1("header", { class: "card__head", children: [
      card.copy.kicker ? /* @__PURE__ */ u$1("p", { class: "copy card__kicker", "data-fit": "kicker", children: card.copy.kicker }) : null,
      /* @__PURE__ */ u$1("span", { class: "card__rule", "aria-hidden": "true" })
    ] }),
    /* @__PURE__ */ u$1("h1", { class: "copy cover__year tnum", "data-fit": "headline", children: year }),
    /* @__PURE__ */ u$1("span", { class: "cover__plinth", "aria-hidden": "true" }),
    sub ? /* @__PURE__ */ u$1("p", { class: "copy cover__sub", "data-fit": "sub", children: sub }) : null,
    /* @__PURE__ */ u$1("span", { class: "card__foot", "aria-hidden": "true" })
  ] });
}
const SUB_SIZE$1 = 56;
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
    const lines = countLines(sub, CONTENT_WIDTH, SUB_SIZE$1);
    if (lines > 2) {
      throw new RenderError(
        `卡片 ${card.id} 的 big-number.sub 在 ${SUB_SIZE$1}px 下占 ${lines} 行, 最多 2 行; 缩短文案, 或把细节挪到另一张卡`
      );
    }
  }
  if (!hasNumber && !headline) {
    throw new RenderError(`卡片 ${card.id} 的 big-number 既没有 number 也没有 headline, 无法出图`);
  }
  return /* @__PURE__ */ u$1("div", { class: "card big-number", children: [
    /* @__PURE__ */ u$1("header", { class: "card__head", children: [
      card.copy.kicker ? /* @__PURE__ */ u$1("p", { class: "copy card__kicker", "data-fit": "kicker", children: card.copy.kicker }) : null,
      /* @__PURE__ */ u$1("span", { class: "card__rule", "aria-hidden": "true" })
    ] }),
    /* @__PURE__ */ u$1("div", { class: "card__body big-number__stack", children: [
      sub ? /* @__PURE__ */ u$1("p", { class: "copy big-number__sub", "data-fit": "sub", children: sub }) : null,
      hasNumber && headline ? /* @__PURE__ */ u$1("p", { class: "copy big-number__headline", "data-fit": "headline", children: headline }) : null,
      /* @__PURE__ */ u$1("p", { class: "copy big-number__value tnum", "data-fit": "number", children: hasNumber ? number : headline })
    ] }),
    /* @__PURE__ */ u$1("span", { class: "card__foot", "aria-hidden": "true" })
  ] });
}
const SIZE = 900;
const CENTER = SIZE / 2;
const OUTER = 400;
const INNER = 170;
const BOUNDS = 430;
const GAP_DEG = 0.35;
const TITLE_SIZE$2 = 96;
const CAPTION_SIZE = 36;
function polar(radius, degrees) {
  const radians = (degrees - 90) * Math.PI / 180;
  return [CENTER + radius * Math.cos(radians), CENTER + radius * Math.sin(radians)];
}
function wedgePath(start, end) {
  const [x1, y1] = polar(OUTER, start);
  const [x2, y2] = polar(OUTER, end);
  const [x3, y3] = polar(INNER, end);
  const [x4, y4] = polar(INNER, start);
  return [
    `M ${x1.toFixed(2)} ${y1.toFixed(2)}`,
    `A ${OUTER} ${OUTER} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`,
    `L ${x3.toFixed(2)} ${y3.toFixed(2)}`,
    `A ${INNER} ${INNER} 0 0 0 ${x4.toFixed(2)} ${y4.toFixed(2)}`,
    "Z"
  ].join(" ");
}
function formatValue(value, unit) {
  return unit === "share" ? `${Math.round(value * 100)}%` : String(Math.round(value));
}
function cardinalTicks(cardId) {
  return [0, 90, 180, 270].map((angle) => {
    const [x1, y1] = polar(412, angle);
    const [x2, y2] = polar(428, angle);
    return /* @__PURE__ */ u$1(
      "line",
      {
        class: "clock__tick",
        x1: x1.toFixed(2),
        y1: y1.toFixed(2),
        x2: x2.toFixed(2),
        y2: y2.toFixed(2)
      },
      `${cardId}-tick${angle}`
    );
  });
}
function Clock({ card }) {
  const series = card.series;
  if (!series || series.axis !== "hour") {
    throw new RenderError(
      `卡片 ${card.id} 的 clock 需要 axis=hour 的 series; 当前 ${series ? `axis=${series.axis}` : "没有 series"}`
    );
  }
  const title = card.copy.headline ?? "";
  if (title && countLines(title, CONTENT_WIDTH, TITLE_SIZE$2) > 1) {
    throw new RenderError(`卡片 ${card.id} 的 clock.headline 在 ${TITLE_SIZE$2}px 下超过 1 行`);
  }
  const caption = card.copy.sub ?? "";
  if (caption && countLines(caption, CONTENT_WIDTH, CAPTION_SIZE) > 2) {
    throw new RenderError(`卡片 ${card.id} 的 clock.sub 在 ${CAPTION_SIZE}px 下超过 2 行`);
  }
  const values = series.values;
  const total = values.reduce((sum, value) => sum + value, 0);
  const max = Math.max(0, ...values);
  const peak = values.indexOf(max);
  const empty = total <= 0;
  return /* @__PURE__ */ u$1("div", { class: "card clock", children: [
    /* @__PURE__ */ u$1("header", { class: "card__head", children: [
      card.copy.kicker ? /* @__PURE__ */ u$1("p", { class: "copy card__kicker", "data-fit": "kicker", children: card.copy.kicker }) : null,
      /* @__PURE__ */ u$1("span", { class: "card__rule", "aria-hidden": "true" }),
      title ? /* @__PURE__ */ u$1("h2", { class: "copy card__title", "data-fit": "headline", children: title }) : null
    ] }),
    /* @__PURE__ */ u$1("div", { class: "card__body clock__body", children: [
      /* @__PURE__ */ u$1("div", { class: "clock__dial", children: /* @__PURE__ */ u$1("svg", { class: "clock__svg", viewBox: `0 0 ${SIZE} ${SIZE}`, role: "img", "aria-label": "24 小时分布", children: [
        /* @__PURE__ */ u$1("circle", { class: "clock__bounds", cx: CENTER, cy: CENTER, r: BOUNDS }),
        cardinalTicks(card.id),
        empty ? /* @__PURE__ */ u$1("circle", { class: "clock__ring", cx: CENTER, cy: CENTER, r: (OUTER + INNER) / 2 }) : values.map((value, hour) => {
          const start = hour * 15;
          const end = (hour + 1) * 15;
          if (value <= 0) {
            const mid = start + 7.5;
            const [x1, y1] = polar(INNER, mid);
            const [x2, y2] = polar(OUTER, mid);
            return /* @__PURE__ */ u$1(
              "line",
              {
                class: "clock__zero",
                x1: x1.toFixed(2),
                y1: y1.toFixed(2),
                x2: x2.toFixed(2),
                y2: y2.toFixed(2)
              },
              `${card.id}-h${hour}`
            );
          }
          const opacity = 0.2 + 0.8 * (value / max);
          return /* @__PURE__ */ u$1(
            "path",
            {
              class: "clock__wedge",
              d: wedgePath(start + GAP_DEG, end - GAP_DEG),
              "fill-opacity": opacity.toFixed(3)
            },
            `${card.id}-h${hour}`
          );
        }),
        /* @__PURE__ */ u$1("circle", { class: "clock__disc", cx: CENTER, cy: CENTER, r: INNER }),
        empty ? /* @__PURE__ */ u$1(S, { children: [
          /* @__PURE__ */ u$1("text", { class: "clock__peak-label", x: CENTER, y: 414, children: "没有可用分布" }),
          /* @__PURE__ */ u$1("text", { class: "clock__peak", x: CENTER, y: 540, children: "—" })
        ] }) : /* @__PURE__ */ u$1(S, { children: [
          /* @__PURE__ */ u$1("text", { class: "clock__peak-label", x: CENTER, y: 414, children: "最活跃小时" }),
          /* @__PURE__ */ u$1("text", { class: "clock__peak tnum", x: CENTER, y: 540, children: [
            String(peak).padStart(2, "0"),
            ":00"
          ] }),
          /* @__PURE__ */ u$1("text", { class: "clock__peak-label", x: CENTER, y: 592, children: series.unit === "share" ? `占 ${formatValue(values[peak], series.unit)}` : `${formatValue(values[peak], series.unit)} 次` })
        ] })
      ] }) }),
      caption ? /* @__PURE__ */ u$1("p", { class: "copy clock__caption", "data-fit": "sub", children: caption }) : null,
      empty ? /* @__PURE__ */ u$1("p", { class: "copy clock__caption", "data-fit": "caveat", children: "窗口内没有可用的时间分布; 细环表示全零, 不是均匀分布。" }) : null
    ] }),
    /* @__PURE__ */ u$1("span", { class: "card__foot", "aria-hidden": "true" })
  ] });
}
const DAY_MS = 864e5;
const TITLE_SIZE$1 = 96;
const SUB_SIZE = 40;
function levelOf(value, max) {
  if (max <= 0 || value <= 0) {
    return 0;
  }
  return Math.min(4, Math.max(1, Math.ceil(value / max * 4)));
}
function buildCells(keys, values, year) {
  const start = Date.UTC(year, 0, 1);
  const end = Date.UTC(year, 11, 31);
  const totalDays = Math.round((end - start) / DAY_MS) + 1;
  const startDow = (new Date(start).getUTCDay() + 6) % 7;
  const cols = Math.ceil((startDow + totalDays) / 7);
  const byDay = /* @__PURE__ */ new Map();
  keys.forEach((key, index) => {
    const [y2, m2, d2] = key.split("-").map(Number);
    const offset = Math.round((Date.UTC(y2, m2 - 1, d2) - start) / DAY_MS);
    if (offset >= 0 && offset < totalDays) {
      byDay.set(offset, values[index] ?? 0);
    }
  });
  const max = Math.max(0, ...byDay.values());
  const cells = [];
  for (let offset = 0; offset < totalDays; offset += 1) {
    const row = (startDow + offset) % 7;
    const column = Math.floor((startDow + offset) / 7);
    const value = byDay.get(offset);
    cells.push({
      column,
      row,
      level: value === void 0 ? 0 : levelOf(value, max),
      empty: value === void 0
    });
  }
  return { cells, cols };
}
function Heatmap({ card, year }) {
  const series = card.series;
  if (!series || series.axis !== "day") {
    throw new RenderError(
      `卡片 ${card.id} 的 heatmap 需要 axis=day 的 series; 当前 ${series ? `axis=${series.axis}` : "没有 series"}`
    );
  }
  const headline = card.copy.headline ?? "";
  if (headline && countLines(headline, CONTENT_WIDTH, TITLE_SIZE$1) > 1) {
    throw new RenderError(`卡片 ${card.id} 的 heatmap.headline 在 ${TITLE_SIZE$1}px 下超过 1 行`);
  }
  const sub = card.copy.sub ?? "";
  if (sub && countLines(sub, CONTENT_WIDTH, SUB_SIZE) > 2) {
    throw new RenderError(`卡片 ${card.id} 的 heatmap.sub 在 ${SUB_SIZE}px 下超过 2 行`);
  }
  const { cells, cols } = buildCells(series.keys, series.values, year);
  const active = cells.filter((cell) => !cell.empty);
  const emptyYear = active.every((cell) => cell.level === 0);
  return /* @__PURE__ */ u$1("div", { class: "card heatmap", children: [
    /* @__PURE__ */ u$1("header", { class: "card__head", children: [
      card.copy.kicker ? /* @__PURE__ */ u$1("p", { class: "copy card__kicker", "data-fit": "kicker", children: card.copy.kicker }) : null,
      /* @__PURE__ */ u$1("span", { class: "card__rule", "aria-hidden": "true" }),
      headline ? /* @__PURE__ */ u$1("h2", { class: "copy card__title", "data-fit": "headline", children: headline }) : null,
      sub ? /* @__PURE__ */ u$1("p", { class: "copy card__sub", "data-fit": "sub", children: sub }) : null
    ] }),
    /* @__PURE__ */ u$1("div", { class: "card__body heatmap__body", children: [
      /* @__PURE__ */ u$1("div", { class: "heatmap__panel", children: [
        /* @__PURE__ */ u$1("div", { class: "heatmap__grid", style: `--cols:${cols}`, "data-cols": cols, children: cells.map((cell, index) => /* @__PURE__ */ u$1(
          "span",
          {
            class: cell.empty ? "heatmap__cell heatmap__cell--empty" : cell.level === 0 ? "heatmap__cell heatmap__cell--zero" : `heatmap__cell heatmap__cell--l${cell.level}`,
            style: `grid-column:${cell.column + 1};grid-row:${cell.row + 1}`,
            "data-empty": cell.empty ? "true" : void 0
          },
          `${card.id}-${index}`
        )) }),
        /* @__PURE__ */ u$1("div", { class: "heatmap__foot", children: [
          /* @__PURE__ */ u$1("span", { children: "逐日事件数" }),
          /* @__PURE__ */ u$1("span", { class: "heatmap__scale", children: [
            /* @__PURE__ */ u$1("span", { children: "少" }),
            /* @__PURE__ */ u$1("span", { class: "heatmap__swatch heatmap__cell--zero" }),
            /* @__PURE__ */ u$1("span", { class: "heatmap__swatch heatmap__cell--l2" }),
            /* @__PURE__ */ u$1("span", { class: "heatmap__swatch heatmap__cell--l4" }),
            /* @__PURE__ */ u$1("span", { children: "多" })
          ] })
        ] })
      ] }),
      emptyYear ? /* @__PURE__ */ u$1("p", { class: "copy heatmap__caveat", "data-fit": "caveat", children: '审查窗口内没有事件; 空格外形表示"未发生", 不代表零值。' }) : null
    ] }),
    /* @__PURE__ */ u$1("span", { class: "card__foot", "aria-hidden": "true" })
  ] });
}
const INDEX_WIDTH = 76;
const VALUE_WIDTH = 220;
const GAP$1 = 28;
const LABEL_WIDTH = CONTENT_WIDTH - INDEX_WIDTH - VALUE_WIDTH - GAP$1 * 2;
const LABEL_SIZE = 56;
const VALUE_SIZE = 72;
const UNIT_SIZE = 34;
const MAX_ROWS = 5;
function unitSuffix(unit) {
  return unit === "count" ? "次" : "";
}
function checkRow(cardId, index, row) {
  const labelLines = countLines(row.label, LABEL_WIDTH, LABEL_SIZE);
  if (labelLines > 2) {
    throw new RenderError(
      `卡片 ${cardId} 的 ranking 第 ${index + 1} 行名称在 ${LABEL_SIZE}px 下占 ${labelLines} 行, 最多 2 行; 缩短名称, 或换一个粒度更粗的实体`
    );
  }
  const suffix = unitSuffix(row.unit);
  const valueWidth = measure(row.value, VALUE_SIZE) + (suffix ? measure(suffix, UNIT_SIZE) + 10 : 0);
  if (valueWidth > VALUE_WIDTH) {
    throw new RenderError(
      `卡片 ${cardId} 的 ranking 第 ${index + 1} 行数值宽 ${Math.round(valueWidth)}px, 超过 ${VALUE_WIDTH}px; 缩短数字, 或把单位挪进名称`
    );
  }
}
function Ranking({ card }) {
  const rows = (card.rows ?? []).slice(0, MAX_ROWS);
  if (rows.length === 0) {
    throw new RenderError(
      `卡片 ${card.id} 的 ranking 没有 rows; 需要一个带 rank_* 事实的 conc.* 洞察`
    );
  }
  rows.forEach((row, index) => checkRow(card.id, index, row));
  const headline = card.copy.headline ?? "";
  if (headline && countLines(headline, CONTENT_WIDTH, 96) > 1) {
    throw new RenderError(`卡片 ${card.id} 的 ranking.headline 在 96px 下超过 1 行`);
  }
  const sub = card.copy.sub ?? "";
  if (sub && countLines(sub, CONTENT_WIDTH, 40) > 2) {
    throw new RenderError(`卡片 ${card.id} 的 ranking.sub 在 40px 下超过 2 行`);
  }
  return /* @__PURE__ */ u$1("div", { class: "card ranking", children: [
    /* @__PURE__ */ u$1("header", { class: "card__head", children: [
      card.copy.kicker ? /* @__PURE__ */ u$1("p", { class: "copy card__kicker", "data-fit": "kicker", children: card.copy.kicker }) : null,
      /* @__PURE__ */ u$1("span", { class: "card__rule", "aria-hidden": "true" }),
      headline ? /* @__PURE__ */ u$1("h2", { class: "copy card__title", "data-fit": "headline", children: headline }) : null,
      sub ? /* @__PURE__ */ u$1("p", { class: "copy card__sub", "data-fit": "sub", children: sub }) : null
    ] }),
    /* @__PURE__ */ u$1("div", { class: "card__body ranking__body", children: /* @__PURE__ */ u$1("ol", { class: "ranking__list", children: rows.map((row, index) => /* @__PURE__ */ u$1("li", { class: "ranking__row", children: [
      /* @__PURE__ */ u$1("span", { class: "ranking__index tnum", "data-fit": `row${index}.index`, children: String(index + 1).padStart(2, "0") }),
      /* @__PURE__ */ u$1("span", { class: "copy ranking__label", "data-fit": `row${index}.label`, children: row.label }),
      /* @__PURE__ */ u$1("span", { class: "ranking__value tnum", "data-fit": `row${index}.value`, children: [
        row.value,
        unitSuffix(row.unit) ? /* @__PURE__ */ u$1("span", { class: "ranking__unit", children: unitSuffix(row.unit) }) : null
      ] })
    ] }, `${card.id}-${index}`)) }) }),
    /* @__PURE__ */ u$1("span", { class: "card__foot", "aria-hidden": "true" })
  ] });
}
const GAP = 20;
const CELL_WIDTH = (CONTENT_WIDTH - GAP) / 2;
const CELL_PAD = 26;
const HERO_PAD = 34;
const CELL_VALUE_SIZE = 72;
const HERO_VALUE_SIZE = 150;
const CELL_LABEL_SIZE = 30;
const HERO_LABEL_SIZE = 38;
const MAX_FACTS = 9;
const TITLE_SIZE = 96;
function SummaryGrid({ card }) {
  const facts = (card.facts ?? []).slice(0, MAX_FACTS);
  if (facts.length === 0) {
    throw new RenderError(
      `卡片 ${card.id} 的 summary-grid 没有 facts; 至少需要 3 条被引洞察`
    );
  }
  const wideLast = facts.length > 2 && facts.length % 2 === 0;
  facts.forEach((fact, index) => {
    const hero = index === 0;
    const wide = wideLast && index === facts.length - 1;
    const valueSize = hero ? HERO_VALUE_SIZE : CELL_VALUE_SIZE;
    const valueWidth = hero ? CONTENT_WIDTH - HERO_PAD * 2 : wide ? CONTENT_WIDTH - CELL_PAD * 2 : CELL_WIDTH - CELL_PAD * 2;
    if (measure(fact.value, valueSize) > valueWidth) {
      throw new RenderError(
        `卡片 ${card.id} 的 summary-grid 第 ${index + 1} 个数值宽 ${Math.round(measure(fact.value, valueSize))}px, 超过 ${valueWidth}px`
      );
    }
    const labelSize = hero ? HERO_LABEL_SIZE : CELL_LABEL_SIZE;
    if (countLines(fact.label, valueWidth, labelSize) > 2) {
      throw new RenderError(
        `卡片 ${card.id} 的 summary-grid 第 ${index + 1} 个标签在 ${labelSize}px 下超过 2 行`
      );
    }
  });
  const title = card.copy.headline ?? "";
  if (title && countLines(title, CONTENT_WIDTH, TITLE_SIZE) > 1) {
    throw new RenderError(`卡片 ${card.id} 的 summary-grid.headline 在 ${TITLE_SIZE}px 下超过 1 行`);
  }
  return /* @__PURE__ */ u$1("div", { class: "card summary-grid", children: [
    /* @__PURE__ */ u$1("header", { class: "card__head", children: [
      card.copy.kicker ? /* @__PURE__ */ u$1("p", { class: "copy card__kicker", "data-fit": "kicker", children: card.copy.kicker }) : null,
      /* @__PURE__ */ u$1("span", { class: "card__rule", "aria-hidden": "true" }),
      title ? /* @__PURE__ */ u$1("h2", { class: "copy card__title", "data-fit": "headline", children: title }) : null
    ] }),
    /* @__PURE__ */ u$1("div", { class: "card__body", children: /* @__PURE__ */ u$1("div", { class: "summary-grid__grid", children: facts.map((fact, index) => /* @__PURE__ */ u$1(
      "div",
      {
        class: [
          "summary-grid__cell",
          index === 0 ? "summary-grid__cell--hero" : "",
          wideLast && index === facts.length - 1 ? "summary-grid__cell--wide" : ""
        ].filter(Boolean).join(" "),
        children: [
          /* @__PURE__ */ u$1("span", { class: "summary-grid__value tnum", "data-fit": `fact${index}.value`, children: fact.value }),
          /* @__PURE__ */ u$1("span", { class: "copy summary-grid__label", "data-fit": `fact${index}.label`, children: fact.label })
        ]
      },
      `${card.id}-${index}`
    )) }) }),
    /* @__PURE__ */ u$1("span", { class: "card__foot", "aria-hidden": "true" })
  ] });
}
const ASPECTS = {
  "9:16": { width: 1080, height: 1920 },
  "4:5": { width: 1080, height: 1350 }
};
const CARD_COMPONENTS = {
  cover: Cover,
  "big-number": BigNumber,
  ranking: Ranking,
  heatmap: Heatmap,
  clock: Clock,
  "summary-grid": SummaryGrid
};
function Card({ card, year }) {
  const Component = CARD_COMPONENTS[card.type];
  if (!Component) {
    throw new RenderError(`卡片 ${card.id} 的类型 ${card.type} 尚未实现`);
  }
  return /* @__PURE__ */ u$1(Component, { card, year });
}
function Stage({
  card,
  aspect,
  year
}) {
  const size = ASPECTS[aspect];
  return /* @__PURE__ */ u$1("section", { class: "slide", children: /* @__PURE__ */ u$1(
    "div",
    {
      class: "stage",
      style: `--stage-w:${size.width};--stage-h:${size.height}`,
      "data-card": card.id,
      "data-card-type": card.type,
      "data-aspect": aspect,
      children: /* @__PURE__ */ u$1(Card, { card, year })
    }
  ) });
}
function Deck({ story, aspect }) {
  return /* @__PURE__ */ u$1("main", { class: "deck", children: story.cards.map((card) => /* @__PURE__ */ u$1(Stage, { card, aspect, year: story.meta.year }, card.id)) });
}
const baseCss = '/* 重置、舞台几何与阅读环境。\r\n *\r\n * 每张卡一屏: 竖向滚动 + scroll-snap。舞台尺寸由内联变量给出\r\n * (--stage-w / --stage-h, 单位 px), 缩放由 main.ts 的 10 行脚本按视口算,\r\n * 计算公式是 min(视口宽 / 舞台宽, 视口高 / 舞台高), 保证任何比例下都不裁切。\r\n *\r\n * **背景只允许画在 .stage 上, 不能画在 .card 上。** 阶段 6c 的安全区断言拿\r\n * "同主题、同尺寸、无卡片内容"的空白舞台做像素基准; 卡片层新增的任何底纹都会\r\n * 在边带里形成差值, 直接判失败。装饰要安全地留在舞台层。\r\n */\r\n\r\n*,\r\n*::before,\r\n*::after {\r\n  box-sizing: border-box;\r\n}\r\n\r\nhtml,\r\nbody {\r\n  margin: 0;\r\n  padding: 0;\r\n}\r\n\r\nbody {\r\n  background: #05050a;\r\n  font-family: var(--font-sans);\r\n  -webkit-font-smoothing: antialiased;\r\n  text-rendering: optimizeLegibility;\r\n}\r\n\r\n.deck {\r\n  /* 100dvh 优先: 手机浏览器地址栏收起时 100vh 会多出一截, 导致一屏放不下一张卡。 */\r\n  height: 100vh;\r\n  height: 100dvh;\r\n  overflow-x: hidden;\r\n  overflow-y: scroll;\r\n  scroll-snap-type: y mandatory;\r\n  overscroll-behavior-y: contain;\r\n}\r\n\r\n.slide {\r\n  position: relative;\r\n  height: 100vh;\r\n  height: 100dvh;\r\n  overflow: hidden;\r\n  scroll-snap-align: start;\r\n  scroll-snap-stop: always;\r\n}\r\n\r\n/* 舞台用绝对定位 + 位移居中, 而不是 flex/grid 居中: 1080px 的子元素会把\r\n * auto 轨道撑到 1080, 于是"居中"其实是在一条 1080 宽的轨道里居中, 结果贴左溢出。\r\n * 绝对定位让子元素不参与父级尺寸计算, 任何视口下都真的居中。 */\r\n.stage {\r\n  position: absolute;\r\n  left: 50%;\r\n  top: 50%;\r\n  flex: none;\r\n  width: calc(var(--stage-w) * 1px);\r\n  height: calc(var(--stage-h) * 1px);\r\n  transform: translate(-50%, -50%) scale(var(--stage-scale, 0.3));\r\n  transform-origin: center center;\r\n  overflow: hidden;\r\n  isolation: isolate;\r\n  background-color: var(--skin-bg);\r\n  background-image: var(--skin-bg-image);\r\n  color: var(--skin-ink);\r\n  font-family: var(--font-sans);\r\n  font-kerning: normal;\r\n}\r\n\r\n/* 第二层光: 左下角一盏冷调补光。单光源的渐变会让整张卡看起来是"贴"在背景上的,\r\n * 两盏不同色温的光才有纵深。 */\r\n.stage::before {\r\n  content: "";\r\n  position: absolute;\r\n  inset: 0;\r\n  z-index: -2;\r\n  background:\r\n    radial-gradient(64% 46% at 8% 104%, rgba(198, 255, 61, 0.09), transparent 66%),\r\n    radial-gradient(52% 40% at 96% 62%, rgba(120, 170, 255, 0.05), transparent 70%);\r\n  pointer-events: none;\r\n}\r\n\r\n/* 纵向栅格: 每 270px 一条 1px 的极淡竖线, 上部可见、向下淡出。\r\n * 它只是"这张纸有刻度"的暗示, 不承载任何数据。 */\r\n.stage::after {\r\n  content: "";\r\n  position: absolute;\r\n  inset: 0;\r\n  z-index: -1;\r\n  background-image: repeating-linear-gradient(\r\n    90deg,\r\n    rgba(255, 255, 255, 0.035) 0 1px,\r\n    transparent 1px 270px\r\n  );\r\n  mask-image: linear-gradient(180deg, #000 0%, rgba(0, 0, 0, 0.35) 58%, transparent 86%);\r\n  pointer-events: none;\r\n}\r\n\r\n/* 卡片: 六张卡共享安全区、左右外边距与一条"抬头 → 正文 → 底栏"的骨架,\r\n * 只换内部排布。 */\r\n.card {\r\n  position: absolute;\r\n  inset: 0;\r\n  display: flex;\r\n  flex-direction: column;\r\n  padding: var(--safe-top) var(--margin) var(--safe-bottom);\r\n}\r\n\r\n/* 数字排版: 等宽数字 + 收紧字距。6c 的测量标记是 data-fit 属性, 不是这个类。 */\r\n.tnum {\r\n  font-variant-numeric: tabular-nums lining-nums;\r\n  letter-spacing: var(--track-tight);\r\n}\r\n\r\n/* 中文按字符断行, 不按空格断行; line-break: strict 让标点不落在行首。 */\r\n.copy {\r\n  margin: 0;\r\n  word-break: break-word;\r\n  overflow-wrap: anywhere;\r\n  line-break: strict;\r\n  text-wrap: pretty;\r\n}\r\n\r\n/* 键盘可达性: 预览页里 Tab 到卡片时给一个可见焦点, 截图不会出现它。 */\r\n.stage:focus-visible {\r\n  outline: 2px solid var(--skin-accent);\r\n  outline-offset: -8px;\r\n}\r\n\r\n::selection {\r\n  background: var(--skin-accent);\r\n  color: #0b0b0f;\r\n}\r\n';
const cardCss = '/* 六张卡共用的版面骨架: 抬头 (kicker / 细分隔线 / 标题 / 副标题) → 正文 → 底栏。\r\n *\r\n * 骨架的意义是让六张卡看起来属于同一本册子: 标题永远从同一条基线上起, 底栏永远\r\n * 压在同一条线上, 只有正文区在变。所以这里只放"跨卡一致"的东西, 任何与具体卡型\r\n * 有关的尺寸都留在各自的文件里。\r\n */\r\n\r\n.card__head {\r\n  display: flex;\r\n  flex: none;\r\n  flex-direction: column;\r\n}\r\n\r\n/* kicker 前面那道短横是整套版式的识别符: 六张卡都在同一位置、同一长度。 */\r\n.card__kicker {\r\n  display: flex;\r\n  align-items: center;\r\n  gap: 18px;\r\n  margin: 0;\r\n  font-size: var(--fs-micro);\r\n  line-height: 1.2;\r\n  letter-spacing: var(--track-wide);\r\n  color: var(--skin-faint);\r\n}\r\n\r\n.card__kicker::before {\r\n  content: "";\r\n  flex: none;\r\n  width: 40px;\r\n  height: 2px;\r\n  background: var(--skin-accent);\r\n}\r\n\r\n/* 细分隔线: 左实右虚, 给抬头一个收口, 又不至于把画面切成两半。 */\r\n.card__rule {\r\n  height: 1px;\r\n  margin-top: var(--rule-gap);\r\n  background: linear-gradient(\r\n    90deg,\r\n    rgba(255, 255, 255, 0.26) 0%,\r\n    rgba(255, 255, 255, 0.08) 58%,\r\n    rgba(255, 255, 255, 0) 100%\r\n  );\r\n}\r\n\r\n.card__title {\r\n  margin: var(--head-gap) 0 0;\r\n  font-size: 96px;\r\n  line-height: 1.06;\r\n  font-weight: 700;\r\n  letter-spacing: -0.02em;\r\n  color: var(--skin-ink);\r\n}\r\n\r\n/* 副标题限宽: 936px 通栏读起来像正文段落, 收到 840px 更像图注。 */\r\n.card__sub {\r\n  max-width: 840px;\r\n  margin: var(--sub-gap) 0 0;\r\n  font-size: var(--fs-caption);\r\n  line-height: 1.5;\r\n  color: var(--skin-muted);\r\n}\r\n\r\n.card__body {\r\n  display: flex;\r\n  flex: 1 1 auto;\r\n  flex-direction: column;\r\n  min-height: 0;\r\n  margin-top: var(--body-gap);\r\n}\r\n\r\n/* 底栏: 一截实心强调色 + 一条淡出细线, 与抬头那道短横呼应, 把版面关起来。\r\n * 留 10px 下边距: 内容底边不贴安全区下沿, 给 6c 的边带扫描留出抗锯齿余量。 */\r\n.card__foot {\r\n  display: flex;\r\n  flex: none;\r\n  align-items: center;\r\n  gap: 18px;\r\n  margin-top: auto;\r\n  padding-bottom: 10px;\r\n}\r\n\r\n.card__foot::before {\r\n  content: "";\r\n  flex: none;\r\n  width: 56px;\r\n  height: 2px;\r\n  background: var(--skin-accent);\r\n}\r\n\r\n.card__foot::after {\r\n  content: "";\r\n  flex: 1 1 auto;\r\n  height: 1px;\r\n  background: linear-gradient(90deg, var(--skin-hairline), rgba(255, 255, 255, 0.02));\r\n}\r\n\r\n/* ---------- 4:5 紧凑模式 ----------\r\n * 舞台从 1920 降到 1350, 安全区仍是上下各 240, 内容高度只剩 870。\r\n * 只下调字号与间距, 不动任何几何 (单元格、楔形、面板圆角)。\r\n */\r\n\r\n.stage[data-aspect="4:5"] .card__kicker {\r\n  gap: 14px;\r\n  font-size: 24px;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .card__kicker::before {\r\n  width: 32px;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .card__rule {\r\n  margin-top: 18px;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .card__title {\r\n  margin-top: 22px;\r\n  font-size: 68px;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .card__sub {\r\n  max-width: 760px;\r\n  margin-top: 16px;\r\n  font-size: 34px;\r\n  line-height: 1.45;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .card__body {\r\n  margin-top: 28px;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .card__foot {\r\n  gap: 14px;\r\n  padding-bottom: 8px;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .card__foot::before {\r\n  width: 40px;\r\n}\r\n';
const bigNumberCss = '/* big-number: 数字压底, 其余三层自下而上递减。\n *\n * 版式是 数字 (320) → headline (140) → sub (56) → kicker。视线落点在最下面那层,\n * 所以正文区用 justify-content: flex-end, 把数字推到离底栏最近的位置。\n *\n * 数字不再直接贴安全区下沿: 底栏接管"底线"的角色, 数字与底栏之间留 28px。\n * 这样每张卡都有同一条收口, 而数字仍然是整屏最重的东西。\n */\n\n.big-number__stack {\n  justify-content: flex-end;\n}\n\n.big-number__sub {\n  max-width: 820px;\n  margin: 0 0 22px;\n  font-size: var(--fs-body);\n  line-height: 1.4;\n  color: var(--skin-muted);\n}\n\n.big-number__headline {\n  margin: 0 0 10px;\n  font-size: var(--fs-h2);\n  line-height: 1.04;\n  font-weight: 600;\n  letter-spacing: -0.02em;\n  color: var(--skin-ink);\n}\n\n.big-number__value {\n  /* line-height 0.9 + 基线补偿: 行盒底落在安全区下沿时, CJK 字形仍会向下溢出。\n   * 补偿值是 token, 换字体只改 tokens.css 里的 --display-baseline-shift。 */\n  margin: 0 0 calc(var(--display-baseline-shift) + 28px);\n  font-size: var(--fs-display);\n  line-height: 0.9;\n  font-weight: 700;\n  color: var(--skin-ink);\n}\n\n.stage[data-aspect="4:5"] .big-number__sub {\n  margin-bottom: 16px;\n  font-size: 44px;\n}\n\n.stage[data-aspect="4:5"] .big-number__headline {\n  margin-bottom: 6px;\n  font-size: 104px;\n}\n\n.stage[data-aspect="4:5"] .big-number__value {\n  margin-bottom: calc(var(--display-baseline-shift) + 18px);\n  font-size: 240px;\n}\n';
const clockCss = '/* clock: 24 段楔形, 午夜在顶端, 顺时针, 每段 15°。\r\n *\r\n * 圆环本身只有一圈细线定界 (r=430), 内圈是一块浅色圆盘, 把"最活跃小时"压在圆心;\r\n * 四个方位刻度让"午夜在顶端"这件事不用文字也读得出来。\r\n * 楔形长度固定, 强度靠透明度 —— 长度会让人误读成"多少小时", 透明度只表达强弱。\r\n */\r\n\r\n.clock__body {\r\n  align-items: center;\r\n  justify-content: center;\r\n  text-align: center;\r\n}\r\n\r\n.clock__dial {\r\n  position: relative;\r\n  display: flex;\r\n  align-items: center;\r\n  justify-content: center;\r\n}\r\n\r\n/* 圆心后面那一团极淡的绿光, 让圆盘从背景里浮出来。 */\r\n.clock__dial::before {\r\n  content: "";\r\n  position: absolute;\r\n  width: 640px;\r\n  height: 640px;\r\n  border-radius: 50%;\r\n  background: radial-gradient(circle, rgba(198, 255, 61, 0.1), transparent 62%);\r\n  pointer-events: none;\r\n}\r\n\r\n.clock__svg {\r\n  position: relative;\r\n  width: 900px;\r\n  height: 900px;\r\n}\r\n\r\n.clock__ring {\r\n  fill: none;\r\n  stroke: var(--skin-accent);\r\n  stroke-width: 3;\r\n  opacity: 0.45;\r\n}\r\n\r\n.clock__bounds {\r\n  fill: none;\r\n  stroke: rgba(255, 255, 255, 0.12);\r\n  stroke-width: 1;\r\n}\r\n\r\n.clock__disc {\r\n  fill: rgba(255, 255, 255, 0.035);\r\n  stroke: rgba(255, 255, 255, 0.08);\r\n  stroke-width: 1;\r\n}\r\n\r\n.clock__wedge {\r\n  fill: var(--skin-accent);\r\n}\r\n\r\n/* 某小时为 0: 楔形退化成一条线。这不是缺数据, 是"确实没有事件"。 */\r\n.clock__zero {\r\n  stroke: var(--skin-accent);\r\n  stroke-width: 3;\r\n  stroke-linecap: round;\r\n  opacity: 0.4;\r\n}\r\n\r\n/* 四个方位刻度: 只需看见"顶上是午夜", 不需要文字。 */\r\n.clock__tick {\r\n  stroke: var(--skin-accent-line);\r\n  stroke-width: 2;\r\n  stroke-linecap: round;\r\n}\r\n\r\n.clock__peak {\r\n  font-size: 120px;\r\n  font-weight: 700;\r\n  letter-spacing: -0.03em;\r\n  fill: var(--skin-ink);\r\n  text-anchor: middle;\r\n}\r\n\r\n.clock__peak-label {\r\n  font-size: 28px;\r\n  letter-spacing: var(--track-wide);\r\n  fill: var(--skin-faint);\r\n  text-anchor: middle;\r\n}\r\n\r\n.clock__caption {\r\n  max-width: 760px;\r\n  margin: 34px auto 0;\r\n  font-size: 36px;\r\n  line-height: 1.45;\r\n  color: var(--skin-muted);\r\n}\r\n\r\n/* 4:5 的正文区只有 687px: 620 的圆盘加图注会顶穿底栏, 收到 560 才留得出气口。 */\r\n.stage[data-aspect="4:5"] .clock__svg {\r\n  width: 560px;\r\n  height: 560px;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .clock__dial::before {\r\n  width: 420px;\r\n  height: 420px;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .clock__caption {\r\n  max-width: 640px;\r\n  margin-top: 14px;\r\n  font-size: 30px;\r\n}\r\n';
const coverCss = '/* cover: 年份是一块实心的字面, 不靠图形撑场。\n *\n * 版面从上到下: kicker → 细分隔线 → 年份 → 一道强调色基座 → 副标题 → 底栏。\n * 基座是这张卡的记忆点: 它把 320px 的字面"托"起来, 而不是让文字浮在渐变里。\n */\n\n.cover__year {\n  margin: 96px 0 0;\n  font-size: var(--fs-display);\n  line-height: 0.82;\n  font-weight: 700;\n  color: var(--skin-ink);\n}\n\n.cover__plinth {\n  width: 240px;\n  height: 3px;\n  margin-top: 44px;\n  background: var(--skin-accent);\n  border-radius: 2px;\n}\n\n.cover__sub {\n  max-width: 880px;\n  margin: 44px 0 0;\n  font-size: var(--fs-lead);\n  line-height: 1.28;\n  color: var(--skin-muted);\n}\n\n/* 封面独占一屏, 底栏给得更重: 168px 的实心条而不是通用的 56px。 */\n.cover .card__foot::before {\n  width: 168px;\n  height: 3px;\n}\n\n.stage[data-aspect="4:5"] .cover__year {\n  margin-top: 72px;\n  font-size: 260px;\n}\n\n.stage[data-aspect="4:5"] .cover__plinth {\n  width: 180px;\n  margin-top: 34px;\n}\n\n.stage[data-aspect="4:5"] .cover__sub {\n  max-width: 720px;\n  margin-top: 34px;\n  font-size: 64px;\n}\n';
const heatmapCss = '/* heatmap: 53×7 的日历格, 装在一个面板里。\r\n *\r\n * 900×118 的格阵单独放在 1080×1920 的画布上会像一条浮着的线。给它一个面板边框\r\n * 与内阴影, 它才成为一件"被装裱起来的图表": 面板宽 932 = 900 + 两侧各 16,\r\n * 居中后左右各留 74px, 仍在 72px 的安全区之内。\r\n *\r\n * 颜色只用一个色相的四个档位 (强调色的 22% / 40% / 68% / 100%), "零"用一层\r\n * 极淡的白, "未发生"完全透明 —— 三者在视觉上必须能分开。\r\n */\r\n\r\n/* 900x118 的格阵很轻, 贴在标题下面会留下大半屏的空白; 垂直居中、并略微上移\r\n * (底部多留 40px), 上下留白才接近, 面板也读得出"被装裱在页面中央"的意图。 */\r\n.heatmap__body {\r\n  justify-content: center;\r\n  padding-bottom: 40px;\r\n}\r\n\r\n.heatmap__panel {\r\n  display: flex;\r\n  flex-direction: column;\r\n  gap: 26px;\r\n  width: fit-content;\r\n  margin: 0 auto;\r\n  padding: 16px;\r\n  border: 1px solid var(--skin-hairline);\r\n  border-radius: var(--radius-panel);\r\n  background: linear-gradient(180deg, rgba(255, 255, 255, 0.055), rgba(255, 255, 255, 0.015));\r\n  /* 负扩散把外阴影收在面板底下: 70px 的柔化会横向漏进左右安全区,\r\n   * 6c 的边带扫描会以 ΔE>2 抓到它。 */\r\n  box-shadow:\r\n    inset 0 1px 0 rgba(255, 255, 255, 0.07),\r\n    0 18px 40px -18px rgba(0, 0, 0, 0.55);\r\n}\r\n\r\n.heatmap__grid {\r\n  display: grid;\r\n  grid-template-columns: repeat(var(--cols), 16px);\r\n  grid-template-rows: repeat(7, 16px);\r\n  gap: 1px;\r\n}\r\n\r\n.heatmap__cell {\r\n  width: 16px;\r\n  height: 16px;\r\n  border-radius: 3px;\r\n  background: rgba(255, 255, 255, 0.06);\r\n}\r\n\r\n/* 窗口之外的日期: 只有一圈 1px 的描边, 与"零值"的实心淡块区分开。 */\r\n.heatmap__cell--empty {\r\n  background: transparent;\r\n  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.05);\r\n}\r\n\r\n.heatmap__cell--zero {\r\n  background: rgba(255, 255, 255, 0.06);\r\n}\r\n\r\n.heatmap__cell--l1 {\r\n  background: rgba(198, 255, 61, 0.24);\r\n}\r\n\r\n.heatmap__cell--l2 {\r\n  background: rgba(198, 255, 61, 0.42);\r\n}\r\n\r\n.heatmap__cell--l3 {\r\n  background: rgba(198, 255, 61, 0.7);\r\n}\r\n\r\n.heatmap__cell--l4 {\r\n  background: rgba(198, 255, 61, 1);\r\n}\r\n\r\n/* 图例是面板的脚注: 一条细线把它和格阵分开, 两端对齐, 读起来像图表的图例而不是\r\n * 挤在角落的注释。 */\r\n.heatmap__foot {\r\n  display: flex;\r\n  align-items: center;\r\n  justify-content: space-between;\r\n  gap: 12px;\r\n  padding: 18px 4px 2px;\r\n  border-top: 1px solid var(--skin-hairline);\r\n  font-size: 26px;\r\n  line-height: 1.2;\r\n  color: var(--skin-faint);\r\n}\r\n\r\n.heatmap__scale {\r\n  display: flex;\r\n  align-items: center;\r\n  gap: 10px;\r\n}\r\n\r\n.heatmap__swatch {\r\n  width: 16px;\r\n  height: 16px;\r\n  border-radius: 3px;\r\n}\r\n\r\n.heatmap__caveat {\r\n  max-width: 760px;\r\n  margin: 26px auto 0;\r\n  font-size: 32px;\r\n  line-height: 1.45;\r\n  text-align: center;\r\n  color: var(--skin-muted);\r\n}\r\n\r\n.stage[data-aspect="4:5"] .heatmap__panel {\r\n  gap: 18px;\r\n  padding: 12px;\r\n  border-radius: 22px;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .heatmap__foot {\r\n  padding-top: 12px;\r\n  font-size: 22px;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .heatmap__caveat {\r\n  margin-top: 20px;\r\n  font-size: 28px;\r\n}\r\n';
const rankingCss = '/* ranking: 3–5 行, 序号 / 名称 / 数值三列。\r\n *\r\n * 行与行之间只有 1px 细线, 靠字号 (56 / 72) 与右对齐的等宽数字建立秩序;\r\n * 第一名用强调色标序号, 其余用淡色 —— 这是整张卡上唯一用色的地方。\r\n */\r\n\r\n.ranking__list {\r\n  display: flex;\r\n  flex-direction: column;\r\n  margin: 0;\r\n  padding: 0;\r\n  list-style: none;\r\n}\r\n\r\n.ranking__body {\r\n  justify-content: center;\r\n}\r\n\r\n.ranking__row {\r\n  display: grid;\r\n  grid-template-columns: 76px minmax(0, 1fr) auto;\r\n  align-items: baseline;\r\n  gap: 28px;\r\n  padding: 30px 0;\r\n  border-top: 1px solid var(--skin-hairline);\r\n}\r\n\r\n.ranking__row:last-child {\r\n  border-bottom: 1px solid var(--skin-hairline);\r\n}\r\n\r\n.ranking__index {\r\n  font-size: var(--fs-caption);\r\n  line-height: 1.2;\r\n  font-weight: 500;\r\n  color: var(--skin-faint);\r\n}\r\n\r\n.ranking__row:first-child .ranking__index {\r\n  color: var(--skin-accent);\r\n}\r\n\r\n.ranking__label {\r\n  min-width: 0;\r\n  font-size: var(--fs-body);\r\n  line-height: 1.26;\r\n  color: var(--skin-ink);\r\n}\r\n\r\n.ranking__value {\r\n  /* 右对齐的数字与内容区右边界齐平; 留 3px 是为了让最后一位的墨迹落在边界内,\r\n   * 而不是压在 1008px 那条线上 (6c 的右带从 1008 开始扫)。 */\r\n  padding-right: 3px;\r\n  text-align: right;\r\n  font-size: 72px;\r\n  line-height: 1.1;\r\n  font-weight: 600;\r\n  color: var(--skin-ink);\r\n  white-space: nowrap;\r\n}\r\n\r\n.ranking__unit {\r\n  margin-left: 10px;\r\n  font-size: 34px;\r\n  font-weight: 400;\r\n  color: var(--skin-muted);\r\n}\r\n\r\n.stage[data-aspect="4:5"] .ranking__row {\r\n  grid-template-columns: 64px minmax(0, 1fr) auto;\r\n  gap: 20px;\r\n  padding: 20px 0;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .ranking__index {\r\n  font-size: 34px;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .ranking__label {\r\n  font-size: 48px;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .ranking__value {\r\n  font-size: 60px;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .ranking__unit {\r\n  font-size: 30px;\r\n}\r\n';
const summaryGridCss = '/* summary-grid: 两列网格, 第一个 fact 占双列。\r\n *\r\n * 层级靠三件事拉开, 而不是靠更多颜色:\r\n * 1) 主角格横跨两列, 数值是其余格子的两倍大;\r\n * 2) 主角格有强调色底与更亮的描边, 其余格只有一层白 4.5%;\r\n * 3) 数值在上、标签在下, 全部左对齐 —— 九宫格里最怕的是居中对齐造成的参差。\r\n */\r\n\r\n.summary-grid__grid {\r\n  display: grid;\r\n  flex: 1 1 auto;\r\n  grid-template-columns: 1fr 1fr;\r\n  gap: 20px;\r\n  align-content: start;\r\n}\r\n\r\n.summary-grid__cell {\r\n  display: flex;\r\n  flex-direction: column;\r\n  gap: 10px;\r\n  min-width: 0;\r\n  padding: 26px 26px 24px;\r\n  border: 1px solid var(--skin-hairline);\r\n  border-radius: var(--radius-cell);\r\n  background: var(--skin-surface);\r\n}\r\n\r\n.summary-grid__cell--hero {\r\n  grid-column: 1 / -1;\r\n  gap: 12px;\r\n  padding: 32px 34px 30px;\r\n  border-color: rgba(198, 255, 61, 0.22);\r\n  background: linear-gradient(135deg, rgba(198, 255, 61, 0.1), rgba(198, 255, 61, 0.02) 62%);\r\n  box-shadow: inset 0 1px 0 rgba(198, 255, 61, 0.14);\r\n}\r\n\r\n.summary-grid__value {\r\n  font-size: 72px;\r\n  line-height: 1.04;\r\n  font-weight: 600;\r\n  color: var(--skin-ink);\r\n}\r\n\r\n.summary-grid__cell--hero .summary-grid__value {\r\n  font-size: 150px;\r\n  font-weight: 700;\r\n}\r\n\r\n.summary-grid__label {\r\n  font-size: 30px;\r\n  line-height: 1.35;\r\n  color: var(--skin-muted);\r\n}\r\n\r\n.summary-grid__cell--hero .summary-grid__label {\r\n  font-size: 38px;\r\n  letter-spacing: 0.04em;\r\n  color: var(--skin-faint);\r\n}\r\n\r\n.stage[data-aspect="4:5"] .summary-grid__grid {\r\n  gap: 8px;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .summary-grid__cell {\r\n  gap: 6px;\r\n  padding: 8px 18px;\r\n  border-radius: 14px;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .summary-grid__cell--hero {\r\n  gap: 8px;\r\n  padding: 12px 24px;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .summary-grid__value {\r\n  font-size: 52px;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .summary-grid__cell--hero .summary-grid__value {\r\n  font-size: 88px;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .summary-grid__label {\r\n  font-size: 24px;\r\n}\r\n\r\n.stage[data-aspect="4:5"] .summary-grid__cell--hero .summary-grid__label {\r\n  font-size: 30px;\r\n}\r\n\r\n/* 偶数个 fact 时最后一格横跨两列, 避免留下半个空格子。 */\r\n.summary-grid__cell--wide {\r\n  grid-column: 1 / -1;\r\n}\r\n\n/* 4:5 的标题字面下缘会压到主角格: 72px 的行盒装不下 96px 的字形墨迹,\n * 这里多留 8px, 让视觉间距回到 20px 以上。 */\n.stage[data-aspect="4:5"] .summary-grid .card__body {\n  margin-top: 36px;\n}\n';
const tokensCss = '/* 设计 token。\r\n *\r\n * 布局一律用绝对像素: 舞台固定 1080x1920 (或 1080x1350), 缩放只发生在 .stage 的\r\n * transform 上。这样 PNG/MP4 阶段的截图与浏览器里看到的是同一套几何, 不需要为\r\n * 两个目标各调一遍。\r\n *\r\n * 字体确定性推迟到 PNG/MP4 阶段 (阶段 7)。HTML 阶段用系统字体栈, 因为:\r\n * 1) 在浏览器里 CJK 字体本来就由系统提供, 随包字体只会让文件变大;\r\n * 2) CJK 子集化是件正经工作 (需要按实际文案裁剪字形), 在还没有像素输出的阶段\r\n *    为它付费没有回报。\r\n * 阶段 7 引入随包 WOFF2 时, 只替换下面的 --font-sans 与其 @font-face, 布局不用动。\r\n * 看到这里没有 @font-face 是**故意的**, 不是漏了。\r\n */\r\n\r\n:root {\r\n  /* 栅格与安全区 */\r\n  --col: 56px;\r\n  --gutter: 24px;\r\n  --margin: 72px;\r\n  --safe-top: 240px;\r\n  --safe-bottom: 240px;\r\n\r\n  /* 字阶 */\r\n  --fs-display: 320px;\r\n  --fs-h1: 220px;\r\n  --fs-h2: 140px;\r\n  --fs-lead: 88px;\r\n  --fs-body: 56px;\r\n  --fs-caption: 40px;\r\n  --fs-micro: 28px;\r\n\r\n  /* 版面骨架: 抬头 (kicker/标题/副标题) 的固定节奏, 六张卡共用 */\r\n  --head-gap: 36px;\r\n  --rule-gap: 24px;\r\n  --sub-gap: 22px;\r\n  --body-gap: 64px;\r\n\r\n  --track-tight: -0.025em;\r\n  --track-wide: 0.22em;\r\n\r\n  /* 巨型数字的视觉底边补偿。line-height 0.9 是几何, 0.12em 是字体相关的修正:\r\n   * 行盒底落在安全区下沿时, CJK 字形仍会向下溢出。换字体后只重测这一个值,\r\n   * 由阶段 6c 的安全区断言验证, 不需要肉眼比对。 */\r\n  --display-baseline-shift: 0.12em;\r\n\r\n  /* 表面与线条: 层次靠这几层叠出来, 而不是靠更多颜色 */\r\n  --skin-surface: rgba(255, 255, 255, 0.045);\r\n  --skin-surface-strong: rgba(255, 255, 255, 0.075);\r\n  --skin-hairline: rgba(255, 255, 255, 0.1);\r\n  --skin-hairline-strong: rgba(255, 255, 255, 0.18);\r\n  --skin-accent-soft: rgba(198, 255, 61, 0.12);\r\n  --skin-accent-line: rgba(198, 255, 61, 0.55);\r\n\r\n  --radius-panel: 28px;\r\n  --radius-cell: 20px;\r\n\r\n  --dur-fast: 160ms;\r\n  --dur-mid: 400ms;\r\n  --dur-slow: 700ms;\r\n  --ease-out: cubic-bezier(0.2, 0.7, 0.1, 1);\r\n\r\n  --font-sans: "Inter Tight", -apple-system, "Segoe UI", "PingFang SC",\r\n    "Microsoft YaHei", "Noto Sans SC", sans-serif;\r\n}\r\n\r\n/* 主题 neon: 暗底、饱和渐变、白色文字、单一强调色。文字不加投影。\r\n *\r\n * muted / faint 不是随手取的透明度: 阶段 6c 会用真实像素算 WCAG 对比度, 而右上角的\r\n * 霓虹绿辉光会把底色抬亮。0.72 / 0.52 是在最亮的那块背景上小字号仍 >= 4.5:1 的下限,\r\n * 调低这两个值会直接把小字打到不合格。 */\r\n:root {\r\n  --skin-bg: #0b0b0f;\r\n  --skin-bg-image: radial-gradient(118% 78% at 82% -8%, rgba(198, 255, 61, 0.2), transparent 58%),\r\n    linear-gradient(158deg, #17171f 0%, #0b0b0f 52%, #06060a 100%);\r\n  --skin-ink: #ffffff;\r\n  --skin-muted: rgba(255, 255, 255, 0.72);\r\n  --skin-faint: rgba(255, 255, 255, 0.52);\r\n  --skin-accent: #c6ff3d;\r\n  --skin-rule: rgba(255, 255, 255, 0.14);\r\n}\r\n';
const STYLES = [
  tokensCss,
  baseCss,
  cardCss,
  coverCss,
  bigNumberCss,
  rankingCss,
  heatmapCss,
  clockCss,
  summaryGridCss
].join("\n");
function assertBaked(story) {
  const seen = [];
  for (const card of story.cards) {
    const values = [
      card.copy.headline,
      card.copy.sub,
      card.copy.kicker,
      card.number,
      ...(card.rows ?? []).flatMap((row) => [row.label, row.value]),
      ...(card.facts ?? []).flatMap((fact) => [fact.label, fact.value])
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
function readyScript() {
  return [
    "<script>(function () {",
    'function mark() { document.documentElement.setAttribute("data-render-ready", "1"); }',
    "function tick() { requestAnimationFrame(function () { requestAnimationFrame(mark); }); }",
    'if (document.readyState === "complete") { tick(); }',
    'else { window.addEventListener("load", tick, { once: true }); }',
    " } )();<\/script>"
  ].join("");
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
    readyScript(),
    `<style>${STYLES}</style>`,
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
