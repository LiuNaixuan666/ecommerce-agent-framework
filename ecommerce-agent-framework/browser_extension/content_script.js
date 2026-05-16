function extractProductContext() {
  const title = document.querySelector('h1, .product-title, .sku-name, .product-name')?.textContent?.trim() || document.title;
  const price = document.querySelector('.price, .product-price, .sku-page-price, .J_price')?.textContent?.trim() || '';
  const stock = document.querySelector('.stock, .inventory, .stock-status, .sold-out, .out-of-stock')?.textContent?.trim() || '';

  return {
    page_url: window.location.href,
    product_name: title,
    price: price,
    stock: stock,
    extra: {
      title_selector: title ? 'h1 or product title' : null,
      scraped_at: new Date().toISOString()
    }
  };
}

async function sendPageContext(context) {
  try {
    const response = await fetch('http://localhost:8000/api/extension/page-context', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(context)
    });
    const data = await response.json();
    console.log('Extension PoC page context response:', data);
    chrome.storage.local.set({ page_context: context });
  } catch (error) {
    console.warn('Failed to send page context to local backend:', error);
  }
}

const context = extractProductContext();
if (context.product_name || context.price || context.stock) {
  sendPageContext(context);
}
