export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;

  const domain = process.env.RAILWAY_PUBLIC_DOMAIN;
  const url = process.env.KEEP_ALIVE_URL || (domain ? `https://${domain}/api/health` : null);

  if (!url) {
    console.log("[keep-alive] disabled — set RAILWAY_PUBLIC_DOMAIN or KEEP_ALIVE_URL to enable");
    return;
  }

  const INTERVAL_MS = 4 * 60 * 1000; // 4 minutes

  const ping = async () => {
    try {
      const res = await fetch(url, { cache: "no-store" });
      console.debug(`[keep-alive] ping → ${url} [${res.status}]`);
    } catch (err) {
      console.warn(`[keep-alive] ping failed: ${err.message}`);
    }
  };

  console.log(`[keep-alive] enabled — pinging ${url} every ${INTERVAL_MS / 1000}s`);
  setInterval(ping, INTERVAL_MS);
}
