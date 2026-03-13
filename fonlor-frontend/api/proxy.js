export const config = { runtime: 'edge' };

export default async function handler(req) {
  if (req.method === 'OPTIONS') {
      return new Response(null, {
            headers: {
                    'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
                                    'Access-Control-Allow-Headers': 'Content-Type',
                                          }
                                              });
                                                }
                                                  const url = new URL(req.url);
                                                    const endpoint = url.searchParams.get('endpoint') || 'BindHistoryInfo';
                                                      const body = await req.text();
                                                        try {
                                                            const res = await fetch('https://www.tefas.gov.tr/api/DB/' + endpoint, {
                                                                  method: 'POST',
                                                                        headers: {
                                                                                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                                                                                        'X-Requested-With': 'XMLHttpRequest',
                                                                                                'Referer': 'https://www.tefas.gov.tr/TarihselVeriler.aspx',
                                                                                                        'Origin': 'https://www.tefas.gov.tr',
                                                                                                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36',
                                                                                                                      },
                                                                                                                            body
                                                                                                                                });
                                                                                                                                    const data = await res.text();
                                                                                                                                        return new Response(data, {
                                                                                                                                              status: res.status,
                                                                                                                                                    headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
                                                                                                                                                        });
                                                                                                                                                          } catch (e) {
                                                                                                                                                              return new Response(JSON.stringify({ error: e.message }), {
                                                                                                                                                                    status: 500,
                                                                                                                                                                          headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
                                                                                                                                                                              });
                                                                                                                                                                                }
                                                                                                                                                                                }
