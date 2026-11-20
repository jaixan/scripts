#!/usr/bin/osascript -l JavaScript
// Progress window for zip2pptx.py / zip2pdf.py / checkexam.py, used by the "Créer PowerPoint depuis ZIP",
// "Créer PDF depuis ZIP" and "Détecter IA dans ZIP" Quick Actions.
// Usage: osascript -l JavaScript zip2pptx-progress.js <python> <zip2pptx.py|zip2pdf.py|checkexam.py> file1.zip [file2.zip ...]
ObjC.import('AppKit');
ObjC.import('QuartzCore');

const KINDS = {
  'zip2pptx.py': { title: 'ZIP → PowerPoint', unit: 'Diapositive', saving: 'Enregistrement du PowerPoint…', args: [] },
  'zip2pdf.py': { title: 'ZIP → PDF', unit: 'Page', saving: 'Enregistrement du PDF…', args: [] },
  'checkexam.py': { title: 'Détection IA', unit: 'Capture analysée', saving: 'Création du rapport…', args: ['--open'] },
};

function run(argv) {
  const [python, script, ...zips] = argv;
  const kind = KINDS[$(script).lastPathComponent.js] || KINDS['zip2pptx.py'];
  const title = kind.title;
  const app = $.NSApplication.sharedApplication;
  app.setActivationPolicy($.NSApplicationActivationPolicyAccessory);

  const W = 420, H = 110;
  const win = $.NSPanel.alloc.initWithContentRectStyleMaskBackingDefer(
    $.NSMakeRect(0, 0, W, H), $.NSWindowStyleMaskTitled, $.NSBackingStoreBuffered, false);
  win.title = title;
  win.level = $.NSFloatingWindowLevel;
  win.center;

  const label = $.NSTextField.labelWithString('');
  label.frame = $.NSMakeRect(20, 64, W - 40, 22);
  label.lineBreakMode = $.NSLineBreakByTruncatingMiddle;
  win.contentView.addSubview(label);

  const detail = $.NSTextField.labelWithString('');
  detail.frame = $.NSMakeRect(20, 14, W - 40, 18);
  detail.font = $.NSFont.systemFontOfSize(11);
  detail.textColor = $.NSColor.secondaryLabelColor;
  win.contentView.addSubview(detail);

  // Hand-drawn bar: NSProgressIndicator's fill animation doesn't advance outside NSApp.run.
  const BAR_W = W - 40;
  const roundedView = (rect, color) => {
    const v = $.NSView.alloc.initWithFrame(rect);
    v.wantsLayer = true;
    v.layer.backgroundColor = color.CGColor;
    v.layer.cornerRadius = 3;
    return v;
  };
  const track = roundedView($.NSMakeRect(20, 44, BAR_W, 6), $.NSColor.quaternaryLabelColor);
  const fill = roundedView($.NSMakeRect(0, 0, 0, 6), $.NSColor.controlAccentColor);
  track.addSubview(fill);
  win.contentView.addSubview(track);
  const setProgress = (frac) => {
    $.CATransaction.begin;
    $.CATransaction.setDisableActions(true);
    fill.frame = $.NSMakeRect(0, 0, Math.round(BAR_W * frac), 6);
    $.CATransaction.commit;
  };

  win.makeKeyAndOrderFront(null);
  app.activateIgnoringOtherApps(true);

  // Let AppKit draw and handle events for a moment.
  const pump = (secs) => {
    const until = $.NSDate.dateWithTimeIntervalSinceNow(secs);
    for (;;) {
      const ev = app.nextEventMatchingMaskUntilDateInModeDequeue($.NSEventMaskAny, until, $.NSDefaultRunLoopMode, true);
      if (ev.isNil()) break;
      app.sendEvent(ev);
    }
    win.displayIfNeeded;
  };

  const fm = $.NSFileManager.defaultManager;
  const results = [];
  zips.forEach((zip, idx) => {
    const name = $(zip).lastPathComponent.js;
    label.stringValue = zips.length > 1 ? `(${idx + 1}/${zips.length}) ${name}` : name;
    detail.stringValue = 'Lecture du ZIP…';
    setProgress(0);
    pump(0.05);

    // Send the script's output to a temp file and poll it, so the window stays responsive.
    const log = $.NSTemporaryDirectory().js + `zip2pptx-${$.NSUUID.UUID.UUIDString.js}.log`;
    fm.createFileAtPathContentsAttributes(log, $(), $());
    const out = $.NSFileHandle.fileHandleForWritingAtPath(log);
    const task = $.NSTask.alloc.init;
    task.executableURL = $.NSURL.fileURLWithPath(python);
    task.arguments = $([script, '--progress', ...kind.args, zip]);
    task.standardOutput = out;
    task.standardError = out;
    const err = $();
    if (!task.launchAndReturnError(err)) {
      results.push({ name, ok: false, msg: `Impossible de lancer Python: ${python}` });
      return;
    }

    const read = () => $.NSString.stringWithContentsOfFileEncodingError(log, $.NSUTF8StringEncoding, null).js || '';
    let shown = null;
    while (task.running) {
      pump(0.1);
      const lines = read().trim().split('\n');
      const last = lines.filter((l) => l.startsWith('PROGRESS ') || l === 'SAVING').pop();
      if (!last || last === shown) continue;
      if (last === 'SAVING') {
        setProgress(1);
        detail.stringValue = kind.saving;
      } else {
        const [, done, total] = last.split(' ').map(Number);
        setProgress(total ? done / total : 0);
        detail.stringValue = `${kind.unit} ${done} sur ${total}`;
      }
      shown = last;
    }
    out.closeFile;

    const text = read().split('\n').filter((l) => l && !l.startsWith('PROGRESS ') && l !== 'SAVING');
    fm.removeItemAtPathError(log, null);
    const ok = task.terminationStatus === 0;
    results.push({ name, ok, msg: (ok ? text.slice(-1) : text.slice(-5)).join('\n') });
  });

  win.close;

  const sa = Application.currentApplication();
  sa.includeStandardAdditions = true;
  for (const r of results) {
    if (r.ok) {
      sa.displayNotification(r.msg, { withTitle: title, soundName: 'Glass' });
    } else {
      sa.activate();
      sa.displayAlert(`Échec pour ${r.name}`, { message: r.msg });
    }
  }
}
