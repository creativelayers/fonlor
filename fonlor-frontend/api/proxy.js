export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();
  const endpoint = req.query.endpoint || 'BindHistoryInfo';
  let body = typeof req.body === 'string' ? req.body : 
    Object.entries(req.body||{}).map(([k,v])=>k+'='+encodeURIComponent(v)).join('&');
  try {
    const r = await fetch('https://www.tefas.gov.tr/api/DB/'+endpoint, {
      method:'POST',
      headers:{
        'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With':'XMLHttpRequest',
        'Referer':'https://www.tefas.gov.tr/TarihselVeriler.aspx',
        'Origin':'https://www.tefas.gov.tr',
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      },
      body
    });
    const data = await r.text();
    res.setHeader('Content-Type','application/json');
    return res.status(r.status).send(data);
  } catch(e) {
    return res.status(500).json({error:e.message});
  }
}
