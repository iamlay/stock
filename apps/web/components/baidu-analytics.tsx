import Script from "next/script";

const DEFAULT_ID = "26d75880bb0baefcaf2906dc951c705b";

export function BaiduAnalytics() {
  const id = process.env.NEXT_PUBLIC_BAIDU_ANALYTICS_ID ?? DEFAULT_ID;
  const vercelEnv = process.env.VERCEL_ENV;
  const enabled = vercelEnv
    ? vercelEnv === "production"
    : process.env.NODE_ENV === "production";

  if (!id || !enabled) return null;

  return (
    <Script id="baidu-analytics" strategy="afterInteractive">
      {`
        var _hmt = _hmt || [];
        (function() {
          var hm = document.createElement("script");
          hm.src = "https://hm.baidu.com/hm.js?${id}";
          var s = document.getElementsByTagName("script")[0];
          s.parentNode.insertBefore(hm, s);
        })();
      `}
    </Script>
  );
}
