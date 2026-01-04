import { useEffect, useRef } from "react";

const SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY;

export default function TurnstileWidget({ onVerify }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!SITE_KEY || !containerRef.current) return;

    let widgetId = null;
    const renderWidget = () => {
      if (!window.turnstile || !containerRef.current) return;
      containerRef.current.innerHTML = "";
      widgetId = window.turnstile.render(containerRef.current, {
        sitekey: SITE_KEY,
        callback: onVerify,
        "error-callback": () => onVerify(""),
        "expired-callback": () => onVerify(""),
      });
    };

    if (window.turnstile) {
      renderWidget();
    } else {
      const interval = setInterval(() => {
        if (window.turnstile) {
          clearInterval(interval);
          renderWidget();
        }
      }, 50);
      return () => clearInterval(interval);
    }

    return () => {
      if (window.turnstile && widgetId) {
        window.turnstile.remove(widgetId);
      }
    };
  }, [onVerify]);

  if (!SITE_KEY) return null;
  return <div ref={containerRef} />;
}
