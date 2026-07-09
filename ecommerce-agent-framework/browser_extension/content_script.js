function normalizeText(selector) {
  const element = document.querySelector(selector);
  if (!element) {
    return '';
  }
  return element.textContent?.trim() || element.value?.trim() || '';
}

function getSkuFromUrl(url) {
  const skuMatch = url.match(/(sku|id)=([0-9]+)/i);
  return skuMatch ? skuMatch[2] : '';
}

function extractProductContext() {
  const url = window.location.href;
  const domain = window.location.hostname.toLowerCase();
  let product_name = document.title || '';
  let price = '';
  let stock = '';
  let sku = getSkuFromUrl(url);

  if (domain.includes('taobao.com') || domain.includes('tmall.com')) {
    product_name = normalizeText('.tb-main-title') || normalizeText('#J_Title .tb-main-title') || normalizeText('#J_Header .tb-main-title') || normalizeText('.product-name');
    price = normalizeText('.tm-price') || normalizeText('.tb-rmb-num') || normalizeText('#J_PromoPriceNum') || normalizeText('#J_PromoPriceNumTip');
    stock = normalizeText('#J_EmStock') || normalizeText('#J_Stock') || normalizeText('.tb-sell-counter') || normalizeText('.tb-amount') || normalizeText('.J_AmountInput');
    sku = sku || document.querySelector('[data-sku]')?.getAttribute('data-sku') || document.querySelector('#J_SkuId')?.value || '';
  } else if (domain.includes('jd.com')) {
    product_name = normalizeText('.sku-name') || normalizeText('#itemInfo .sku-name') || normalizeText('.sku-name strong');
    price = normalizeText('.price') || normalizeText('#jd-price') || normalizeText('.J_price') || normalizeText('.p-price .price');
    stock = normalizeText('#stock .p-stock') || normalizeText('.p-state') || normalizeText('.p-quantity') || normalizeText('.stock-state') || normalizeText('.btn-special');
    sku = sku || document.querySelector('[data-sku]')?.getAttribute('data-sku') || document.querySelector('#wareId')?.value || '';
  } else {
    product_name = normalizeText('h1') || normalizeText('.product-title') || normalizeText('.sku-name') || normalizeText('.product-name');
    price = normalizeText('.price') || normalizeText('.product-price') || normalizeText('.sku-page-price') || normalizeText('.J_price');
    stock = normalizeText('.stock') || normalizeText('.inventory') || normalizeText('.stock-status') || normalizeText('.sold-out') || normalizeText('.out-of-stock');
  }

  return {
    page_url: url,
    product_name,
    sku,
    price,
    stock,
    extra: {
      page_domain: domain,
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
if (context.product_name || context.price || context.stock || context.sku) {
  sendPageContext(context);
}
