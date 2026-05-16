async function getStoredPageContext() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['page_context'], (result) => {
      resolve(result.page_context || null);
    });
  });
}

async function sendPageChat(userQuery, pageContext) {
  try {
    const body = {
      merchant_id: 'default',
      conversation_id: null,
      page_context: pageContext,
      user_query: userQuery
    };
    const response = await fetch('http://localhost:8000/api/extension/page-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    return await response.json();
  } catch (error) {
    return { error: error.message || String(error) };
  }
}

async function updateResult(text) {
  document.getElementById('result').textContent = text;
}

document.getElementById('sendButton').addEventListener('click', async () => {
  const userQuery = document.getElementById('userQuery').value.trim();
  if (!userQuery) {
    updateResult('请先输入问题。');
    return;
  }
  updateResult('正在发送请求...');

  const pageContext = await getStoredPageContext();
  if (!pageContext) {
    updateResult('未找到页面上下文，请先访问商品页面并等待内容脚本提取。');
    return;
  }

  const result = await sendPageChat(userQuery, pageContext);
  updateResult(JSON.stringify(result, null, 2));
});
