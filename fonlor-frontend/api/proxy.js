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

  const params = Object.fromEntries(new URLSearchParams(body));

  function parseDate(s) {
    if (!s) return null;
    const [d,m,y] = s.split('.');
    return new Date(parseInt(y), parseInt(m)-1, parseInt(d));
  }
  function formatDate(d) {
    return `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${d.getFullYear()}`;
  }

  const tefasHeaders = {
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'X-Requested-With': 'XMLHttpRequest',
    'Referer': 'https://www.tefas.gov.tr/TarihselVeriler.aspx',
    'Origin': 'https://www.tefas.gov.tr',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
  };

  async function fetchOne(chunkBody) {
    const controller = new AbortController();
    const t = setTimeout(() => controller.abort(), 10000);
    try {
      const r = await fetch('https://www.tefas.gov.tr/api/DB/' + endpoint, {
        method: 'POST', headers: tefasHeaders, body: chunkBody, signal: controller.signal
      });
      clearTimeout(t);
      const text = await r.text();
      try { return JSON.parse(text); } catch(e) { return null; }
    } catch(e) { clearTimeout(t); return null; }
  }

  const startDate = parseDate(params.bastarih);
  const endDate = parseDate(params.bittarih);
  const diffDays = startDate && endDate ? Math.round((endDate - startDate) / 86400000) : 0;

  try {
    if (diffDays > 90 && startDate && endDate) {
      // Paralel chunk'lar - her biri 80 gün, hepsi aynı anda
      const chunks = [];
      let cur = new Date(startDate);
      while (cur <= endDate) {
        const chunkEnd = new Date(Math.min(cur.getTime() + 80 * 86400000, endDate.getTime()));
        const cp = new URLSearchParams(params);
        cp.set('bastarih', formatDate(cur));
        cp.set('bittarih', formatDate(chunkEnd));
        chunks.push(cp.toString());
        cur = new Date(chunkEnd.getTime() + 86400000);
      }

      // Hepsini paralel çek
      const results = await Promise.all(chunks.map(c => fetchOne(c)));
      const allData = results.flatMap(r => r?.data || []);

      res.setHeader('Content-Type', 'application/json');
      return res.status(200).json({ data: allData });
    }

    // Normal tek sorgu
    const result = await fetchOne(body);
    if (result) {
      res.setHeader('Content-Type', 'application/json');
      return res.status(200).json(result);
    }
    return res.status(500).json({ error: 'no data' });
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
