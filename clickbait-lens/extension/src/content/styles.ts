/**
 * Overlay styles.
 *
 * Kept as a string rather than a `.css` import so the content script stays a
 * single self-contained file, and injected into a shadow root so the host
 * page's stylesheet can't reach it (and ours can't reach the page).
 */
export const OVERLAY_CSS = `
:host {
  all: initial;
}
* {
  box-sizing: border-box;
}
.root {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 2147483647;
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  font-size: 13px;
  line-height: 1.45;
  color: #16181d;
}
.badge {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px 8px 10px;
  border: 0;
  border-radius: 999px;
  background: #16181d;
  color: #fff;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.28);
  cursor: pointer;
  font: inherit;
}
.badge:hover { background: #23262e; }
.badge:focus-visible { outline: 2px solid #ffc43d; outline-offset: 2px; }
.dot {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 12px;
  color: #16181d;
}
.dot.clean { background: #7ddc9a; }
.dot.low { background: #b9e08a; }
.dot.moderate { background: #ffc43d; }
.dot.high { background: #ff7b6b; }
.badge-label { display: flex; flex-direction: column; align-items: flex-start; }
.badge-label strong { font-size: 12px; font-weight: 600; }
.badge-label span { font-size: 11px; opacity: 0.72; }

.panel {
  width: 380px;
  max-height: min(72vh, 640px);
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.3);
  overflow: hidden;
}
.panel-head {
  padding: 14px 16px;
  background: #16181d;
  color: #fff;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.panel-head h1 { margin: 0; font-size: 14px; font-weight: 650; }
.panel-head p { margin: 2px 0 0; font-size: 11px; opacity: 0.7; }
.close {
  margin-left: auto;
  background: transparent;
  border: 0;
  color: #fff;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  opacity: 0.7;
  padding: 2px 4px;
}
.close:hover { opacity: 1; }

.tabs { display: flex; border-bottom: 1px solid #e6e8ec; background: #f7f8fa; }
.tabs button {
  flex: 1;
  padding: 9px 4px;
  border: 0;
  background: transparent;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
  color: #5a6069;
  border-bottom: 2px solid transparent;
}
.tabs button[aria-selected="true"] { color: #16181d; font-weight: 600; border-bottom-color: #ffc43d; }

.body { overflow-y: auto; padding: 12px 14px 16px; }
.empty { color: #6b727c; padding: 10px 2px; }

.score-row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.score-num { font-size: 26px; font-weight: 700; }
.score-meta { font-size: 11px; color: #6b727c; }

.signal {
  border: 1px solid #e6e8ec;
  border-radius: 10px;
  padding: 10px 11px;
  margin-bottom: 8px;
  background: #fff;
}
.signal-head { display: flex; align-items: center; gap: 8px; }
.signal-head strong { font-size: 12.5px; }
.sev {
  margin-left: auto;
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 999px;
  background: #f1f2f5;
  color: #4a505a;
}
.sev.hot { background: #ffe0dc; color: #a32d1c; }
.signal p { margin: 6px 0 0; font-size: 12px; color: #454b55; }
.quote {
  margin-top: 7px;
  padding: 7px 9px;
  border-left: 3px solid #ffc43d;
  background: #fffaed;
  font-size: 11.5px;
  color: #3d424a;
  cursor: pointer;
  border-radius: 0 6px 6px 0;
  width: 100%;
  text-align: left;
  font-family: inherit;
}
.quote:hover { background: #fff3d1; }
.quote small { display: block; margin-top: 3px; color: #8a7330; font-size: 10px; }

.claim { border: 1px solid #e6e8ec; border-radius: 10px; padding: 10px 11px; margin-bottom: 8px; }
.claim-text { margin: 0 0 6px; font-size: 12.5px; }
.chips { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; }
.chip {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 999px;
  background: #eef0f4;
  color: #4a505a;
}
.chip.prediction { background: #e2ecff; color: #1d4a9c; }
.chip.true, .chip.mostly_true { background: #dbf5e3; color: #16663a; }
.chip.false, .chip.mostly_false { background: #ffe0dc; color: #a32d1c; }
.chip.mixed { background: #fff2cf; color: #85631a; }

.actions { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
button.action {
  font: inherit;
  font-size: 11px;
  padding: 5px 10px;
  border-radius: 7px;
  border: 1px solid #d3d7de;
  background: #fff;
  cursor: pointer;
  color: #16181d;
}
button.action:hover { background: #f3f4f7; }
button.action.primary { background: #16181d; color: #fff; border-color: #16181d; }
button.action.primary:hover { background: #2a2e37; }
button.action:disabled { opacity: 0.55; cursor: progress; }

.verdict { margin-top: 9px; padding: 9px 10px; background: #f7f8fa; border-radius: 8px; }
.verdict h4 { margin: 0 0 4px; font-size: 11.5px; }
.verdict p { margin: 0 0 6px; font-size: 11.5px; color: #4a505a; }
.evidence { margin: 0; padding: 0; list-style: none; }
.evidence li { padding: 5px 0; border-top: 1px solid #e6e8ec; font-size: 11px; }
.evidence a { color: #1d4a9c; text-decoration: none; font-weight: 600; }
.evidence a:hover { text-decoration: underline; }
.evidence .why { color: #6b727c; display: block; margin-top: 2px; }
.stance { font-weight: 700; }
.stance.pos { color: #16663a; }
.stance.neg { color: #a32d1c; }

.author { border: 1px solid #e6e8ec; border-radius: 10px; padding: 11px 12px; margin-bottom: 9px; }
.author-head { display: flex; align-items: center; gap: 10px; }
.trust-ring {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 14px;
  flex: none;
  color: #16181d;
}
.author-head h3 { margin: 0; font-size: 13px; }
.author-head span { font-size: 11px; color: #6b727c; }
.bars { margin-top: 9px; display: grid; gap: 5px; }
.bar { display: grid; grid-template-columns: 96px 1fr 34px; gap: 7px; align-items: center; font-size: 10.5px; }
.bar .track { height: 6px; background: #eef0f4; border-radius: 4px; overflow: hidden; }
.bar .fill { height: 100%; background: #16181d; }
.notes { margin: 9px 0 0; padding-left: 16px; font-size: 11px; color: #5a6069; }
.notes li { margin-bottom: 2px; }

.error {
  margin: 0;
  padding: 10px 12px;
  background: #ffe0dc;
  color: #a32d1c;
  font-size: 11.5px;
}
.foot {
  padding: 8px 14px;
  border-top: 1px solid #e6e8ec;
  font-size: 10.5px;
  color: #8a9099;
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
`;
