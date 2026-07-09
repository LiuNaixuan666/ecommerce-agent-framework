# Browser Extension PoC

这是一个用于演示浏览器扩展与本地 FastAPI 后端交互的最简 PoC。

## 设计思想
- `content_script.js` 在页面加载后提取商品标题、价格、库存等信息。
- 提取到的上下文发送到本地接口 `http://localhost:8000/api/extension/page-context`。
- 支持 Taobao/天猫 和 JD 平台的商品页面 DOM 规则抽取。
- `popup.html` 提供一个输入框，用户可以输入问题并将页面上下文一起发送到 `http://localhost:8000/api/extension/page-chat`。

## 安装步骤
1. 在 Chrome/Edge 中打开扩展管理页面。
2. 开启“开发者模式”。
3. 选择“加载已解压的扩展程序”，指向本目录。
4. 访问商品页面，等待扩展提取页面上下文。
5. 点击扩展图标，输入问题并发送。
