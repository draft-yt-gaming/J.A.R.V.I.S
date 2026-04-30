(() => {
  const clone = document.body ? document.body.cloneNode(true) : null;
  if (!clone) {
    return { title: document.title, url: location.href, text: "" };
  }

  clone.querySelectorAll("script, style, noscript, svg, canvas, iframe, nav, footer").forEach((node) => node.remove());
  const text = (clone.innerText || "")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
    .slice(0, 30000);

  return {
    title: document.title || "Sans titre",
    url: location.href,
    text,
  };
})();
