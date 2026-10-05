// Injected before any page script runs (chrome-devtools-mcp initScript).
//
// 1. Seeded Math.random: an unseeded world builds a different island on every
//    reload, so views captured across reloads would not show the same world.
// 2. window.__wb: Three.js announces every Scene and WebGLRenderer it creates
//    to window.__THREE_DEVTOOLS__ (the devtools-extension hook). Listening
//    there gives us scene/renderer/camera without editing the model's code.
// 3. window.__WB_TIME: ?wb_tod=<0..1>&wb_season=<0..3> from the URL. The
//    daytime preview (preview.py) patches the world's own clock to read this.
(() => {
  let s = 1337 >>> 0;
  Math.random = () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };

  const q = new URLSearchParams(location.search);
  const num = (k) => (q.has(k) ? Number(q.get(k)) : null);
  const tod = num('wb_tod');
  const season = num('wb_season');
  if (tod !== null || season !== null) window.__WB_TIME = { tod, season };

  const wb = (window.__wb = { scenes: [], renderers: [], camera: null, scene: null });
  const hub = new EventTarget();
  hub.addEventListener('observe', (e) => {
    const o = e.detail;
    if (o && o.isScene) wb.scenes.push(o);
    if (o && typeof o.render === 'function' && o.domElement) {
      wb.renderers.push(o);
      const render = o.render.bind(o);
      o.render = (scene, camera) => {
        wb.camera = camera;
        wb.scene = scene;
        return render(scene, camera);
      };
    }
  });
  window.__THREE_DEVTOOLS__ = hub;
})();
