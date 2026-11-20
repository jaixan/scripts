// Bookmarklet : capture le post Reddit à l'écran et le télécharge en fichier .md
// Source lisible. Pour générer le bookmarklet :
//   node -e 'console.log("javascript:"+encodeURIComponent(require("fs").readFileSync("reddit2md-bookmarklet.js","utf8")))'
(() => {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const today = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;

  // Choisit l'élément le plus visible dans la fenêtre (utile dans un fil d'accueil)
  const mostVisible = (els) => {
    let best = null, bestArea = -1;
    for (const el of els) {
      const r = el.getBoundingClientRect();
      const h = Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(r.top, 0));
      if (h > bestArea) { bestArea = h; best = el; }
    }
    return best;
  };

  let title = '', body = null;
  const post = mostVisible(document.querySelectorAll('shreddit-post'));
  if (post) {
    // Nouveau Reddit
    title = post.getAttribute('post-title') || post.querySelector('[slot="title"]')?.innerText || '';
    body = post.querySelector('[slot="text-body"]') ||
      document.querySelector('[id$="-post-rtjson-content"]');
  } else {
    // Old Reddit
    const thing = mostVisible(document.querySelectorAll('.thing.link'));
    if (thing) {
      title = thing.querySelector('a.title')?.innerText || '';
      body = thing.querySelector('.usertext-body .md');
    }
  }
  if (!title) title = document.querySelector('h1')?.innerText || document.title;
  title = title.trim();

  // Conversion HTML -> Markdown (basique)
  const md = (n) => {
    if (n.nodeType === 3) return n.textContent.replace(/\s+/g, ' ');
    if (n.nodeType !== 1) return '';
    const kids = () => [...n.childNodes].map(md).join('');
    const tag = n.tagName.toLowerCase();
    switch (tag) {
      case 'p': return kids().trim() + '\n\n';
      case 'br': return '\n';
      case 'strong': case 'b': return '**' + kids() + '**';
      case 'em': case 'i': return '*' + kids() + '*';
      case 'del': case 's': return '~~' + kids() + '~~';
      case 'a': return '[' + kids() + '](' + n.href + ')';
      case 'img': return '![' + (n.alt || '') + '](' + n.src + ')';
      case 'code': return n.closest('pre') ? n.textContent : '`' + n.textContent + '`';
      case 'pre': return '```\n' + n.textContent.replace(/\n$/, '') + '\n```\n\n';
      case 'h1': case 'h2': case 'h3': case 'h4': case 'h5': case 'h6':
        return '#'.repeat(+tag[1]) + ' ' + kids().trim() + '\n\n';
      case 'blockquote':
        return kids().trim().split('\n').map((l) => '> ' + l).join('\n') + '\n\n';
      case 'ul': case 'ol':
        return [...n.children].filter((li) => li.tagName === 'LI')
          .map((li, i) => (tag === 'ol' ? `${i + 1}. ` : '- ') + md(li).trim().replace(/\n/g, '\n   '))
          .join('\n') + '\n\n';
      case 'hr': return '---\n\n';
      case 'script': case 'style': case 'button': case 'svg': return '';
      default: return kids();
    }
  };
  const text = body ? md(body).replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim() : '';

  const clean = (s) => s.replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();

  // Cherche aussi dans les shadow DOM (composants shreddit-*)
  const deepAll = (root, sel) => {
    const out = [...root.querySelectorAll(sel)];
    for (const el of root.querySelectorAll('*')) if (el.shadowRoot) out.push(...deepAll(el.shadowRoot, sel));
    return out;
  };
  const isUpvoted = (el) => {
    if (!el) return false;
    for (const a of ['vote-state', 'vote-type', 'votestate', 'user-vote'])
      if (/up/i.test(el.getAttribute(a) || '')) return true;
    const scope = el.shadowRoot ? [el, el.shadowRoot] : [el];
    return scope.some((r) => deepAll(r, 'button[upvote], button[aria-label*="pvote" i]').some((b) =>
      b.getAttribute('aria-pressed') === 'true' || b.hasAttribute('active') || b.hasAttribute('upvoted')));
  };

  // Commentaires upvotés (seulement ceux chargés dans la page)
  const comments = [];
  if (post) {
    for (const c of document.querySelectorAll('shreddit-comment')) {
      const row = [...c.children].find((k) => k.tagName.toLowerCase() === 'shreddit-comment-action-row');
      if (!isUpvoted(c) && !isUpvoted(row)) continue;
      const cb = [...c.children].find((k) => k.getAttribute('slot') === 'comment') ||
        document.getElementById(c.getAttribute('thingid') + '-comment-rtjson-content');
      if (cb) comments.push({ author: c.getAttribute('author') || '', text: clean(md(cb)) });
    }
  } else {
    for (const c of document.querySelectorAll('.thing.comment')) {
      const entry = c.querySelector(':scope > .entry');
      const mid = c.querySelector(':scope > .midcol');
      if (!entry || !mid?.classList.contains('likes')) continue;
      const cb = entry.querySelector('.usertext-body .md');
      if (cb) comments.push({ author: entry.querySelector('.author')?.innerText || '', text: clean(md(cb)) });
    }
  }
  const commentsMd = comments
    .map((c) => '\n\n---\n\n' + (c.author ? `**u/${c.author}**\n\n` : '') + c.text)
    .join('');

  const content = `---\nis read: false\ntags:\ncreated: ${today}\n---\n\n${text}${commentsMd}\n`;

  // macOS interdit « : » et « / » ; on retire aussi les caractères que les navigateurs remplacent par « _ »
  const name = title
    .replace(/[\/:\\?*"<>|\x00-\x1f\x7f]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^\.+/, '')
    .slice(0, 200) || 'reddit-post';

  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([content], { type: 'text/markdown;charset=utf-8' }));
  a.download = name + '.md';
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
})();
