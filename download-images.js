// Download all screen-monitoring screenshots for the selected student on exam.net as one .zip.
// Usage: open the student, click the "Skjermovervåking" tab, press Cmd+Option+J (DevTools console),
// paste this whole file, press Enter. Keep the tab visible until "Done" is logged.
(async () => {
  const DRY_RUN = false;        // true = build the zip but don't download it
  const STEP_WAIT_MS = 400;     // wait after each scroll step for screenshots to decrypt/render

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const scroller = document.querySelector('.ScreenMonitoringHistory__container');
  if (!scroller) throw new Error('Open the "Skjermovervåking" tab first.');

  // The list is virtualized: only ~20 screenshots exist in the DOM at a time,
  // so scroll through it and grab each image while it is rendered.
  const shots = new Map(); // caption -> Blob
  const studentId = new URLSearchParams(location.search).get('student') || 'student';

  const studentName = document.querySelector('.StudentOverviewStudentInfo__name')?.innerText.trim() || null;
  const safe = (s) => s.replace(/[\\/:*?"<>|]/g, '-').trim();
  const zipName = `${safe(studentName || `student_${studentId}`)}.zip`;
  console.log(`Student: ${studentName ?? '(name not found, using id)'}`);

  const grabVisible = async () => {
    for (const item of scroller.querySelectorAll('.ScreenMonitoringHistory__screenshot_item')) {
      const caption = item.innerText.trim();
      const img = item.querySelector('img');
      if (!caption || shots.has(caption) || !img?.src.startsWith('blob:')) continue;
      try {
        shots.set(caption, await (await fetch(img.src)).blob());
      } catch (e) {
        // blob not ready yet; it will be retried on the next pass
      }
    }
  };

  scroller.scrollTop = 0;
  await sleep(STEP_WAIT_MS * 2);
  let lastTop = -1;
  while (true) {
    await sleep(STEP_WAIT_MS);
    await grabVisible();
    console.log(`Collected ${shots.size} screenshots...`);
    if (scroller.scrollTop === lastTop) break; // reached the bottom
    lastTop = scroller.scrollTop;
    scroller.scrollTop += scroller.clientHeight * 0.8;
  }
  await sleep(STEP_WAIT_MS * 3);
  await grabVisible();
  console.log(`Collected ${shots.size} screenshots total.`);
  if (!shots.size) return;

  // Minimal store-only (uncompressed) zip writer, so no external library is needed.
  const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc32 = (buf) => {
    let c = 0xffffffff;
    for (let i = 0; i < buf.length; i++) c = crcTable[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  // The decrypted blobs are typed text/plain, so detect the format from the file header.
  const ext = (d) => {
    const head = String.fromCharCode(...d.subarray(0, 12));
    if (head.startsWith('RIFF') && head.slice(8) === 'WEBP') return 'webp';
    if (head.startsWith('\x89PNG')) return 'png';
    if (d[0] === 0xff && d[1] === 0xd8) return 'jpg';
    return 'bin';
  };

  const parts = [];
  const central = [];
  let offset = 0;
  for (const [caption, blob] of [...shots].sort(([a], [b]) => a.localeCompare(b))) {
    const data = new Uint8Array(await blob.arrayBuffer());
    // Name each file after the timestamp shown under the screenshot (colons aren't allowed in filenames).
    const stamp = caption.match(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/)?.[0] ?? caption;
    const name = new TextEncoder().encode(`${safe(stamp)}.${ext(data)}`);
    const crc = crc32(data);

    const local = new DataView(new ArrayBuffer(30));
    local.setUint32(0, 0x04034b50, true);
    local.setUint16(4, 20, true);
    local.setUint32(14, crc, true);
    local.setUint32(18, data.length, true);
    local.setUint32(22, data.length, true);
    local.setUint16(26, name.length, true);
    parts.push(local, name, data);

    const cen = new DataView(new ArrayBuffer(46));
    cen.setUint32(0, 0x02014b50, true);
    cen.setUint16(4, 20, true);
    cen.setUint16(6, 20, true);
    cen.setUint32(16, crc, true);
    cen.setUint32(20, data.length, true);
    cen.setUint32(24, data.length, true);
    cen.setUint16(28, name.length, true);
    cen.setUint32(42, offset, true);
    central.push(cen, name);

    offset += 30 + name.length + data.length;
  }
  const centralSize = central.reduce((s, p) => s + p.byteLength, 0);
  const end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true);
  end.setUint16(8, shots.size, true);
  end.setUint16(10, shots.size, true);
  end.setUint32(12, centralSize, true);
  end.setUint32(16, offset, true);

  const zip = new Blob([...parts, ...central, end], { type: 'application/zip' });
  if (DRY_RUN) return { zipName, count: shots.size, zipBytes: zip.size, first: [...shots.keys()].sort()[0], last: [...shots.keys()].sort().at(-1) };
  const a = document.createElement('a');
  a.href = URL.createObjectURL(zip);
  a.download = zipName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 60000);
  console.log(`Done. Saved ${shots.size} screenshots to ${a.download} (${(zip.size / 1e6).toFixed(1)} MB).`);
})();
