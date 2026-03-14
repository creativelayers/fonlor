export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const endpoint = req.query.endpoint || 'BindHistoryInfo';

  let body = '';
  if (typeof req.body === 'string') {
    body = req.body;
  } else if (req.body && typeof req.body === 'object') {
    body = Object.entries(req.body).map(([k,v]) => k + '=' + encodeURIComponent(v)).join('&');
  }

  try {
    // 25 saniyelik timeout - Vercel 30s limiti içinde kalmak için
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 25000);

    const response = await fetch('https://www.tefas.gov.tr/api/DB/' + endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'https://www.tefas.gov.tr/TarihselVeriler.aspx',
        'Origin': 'https://www.tefas.gov.tr',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'tr-TR,tr;q=0.9',
      },
      body,
      signal: controller.signal,
    });

    clearTimeout(timeout);
    const data = await response.text();
    res.setHeader('Content-Type', 'application/json');
    return res.status(response.status).send(data);
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
