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

  // Parametreleri parse et
  const params = Object.fromEntries(new URLSearchParams(body));
  const bastarih = params.bastarih;
  const bittarih = params.bittarih;

  // Tarih farkı 180 günden fazlaysa chunklara böl
  function parseDate(s) {
    if (!s) return null;
    const [d,m,y] = s.split('.');
    return new Date(y, m-1, d);
  }
  function formatDate(d) {
    return `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${d.getFullYear()}`;
  }

  const startDate = parseDate(bastarih);
  const endDate = parseDate(bittarih);
  const diffDays = startDate && endDate ? (endDate - startDate) / 86400000 : 0;

  const headers = {
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'X-Requested-With': 'XMLHttpRequest',
    'Referer': 'https://www.tefas.gov.tr/TarihselVeriler.aspx',
    'Origin': 'https://www.tefas.gov.tr',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'tr-TR,tr;q=0.9',
  };

  async function fetchChunk(chunkBody) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    try {
      const r = await fetch('https://www.tefas.gov.tr/api/DB/' + endpoint, {
        method: 'POST', headers, body: chunkBody, signal: controller.signal
      });
      clearTimeout(timeout);
      const text = await r.text();
      try { return JSON.parse(text); } catch(e) { return null; }
    } catch(e) {
      clearTimeout(timeout);
      return null;
    }
  }

  try {
    // 180 günden uzun sorguları 80'er günlük parçalara böl
    if (diffDays > 180 && startDate && endDate) {
      const allData = [];
      let cur = new Date(startDate);
      const chunkSize = 80;

      while (cur < endDate) {
        const chunkEnd = new Date(Math.min(cur.getTime() + chunkSize * 86400000, endDate.getTime()));
        const chunkParams = new URLSearchParams(params);
        chunkParams.set('bastarih', formatDate(cur));
        chunkParams.set('bittarih', formatDate(chunkEnd));
        const result = await fetchChunk(chunkParams.toString());
        if (result?.data) allData.push(...result.data);
        cur = new Date(chunkEnd.getTime() + 86400000);
      }

      res.setHeader('Content-Type', 'application/json');
      return res.status(200).json({ data: allData });
    }

    // Normal sorgu
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 25000);
    const response = await fetch('https://www.tefas.gov.tr/api/DB/' + endpoint, {
      method: 'POST', headers, body, signal: controller.signal
    });
    clearTimeout(timeout);
    const data = await response.text();
    res.setHeader('Content-Type', 'application/json');
    return res.status(response.status).send(data);
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
