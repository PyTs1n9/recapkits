/** 渲染期错误: 交给 Python 侧原样打印, 不做静默降级。 */
export class RenderError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RenderError";
  }
}
