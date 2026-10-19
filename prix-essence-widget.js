// Variables used by Scriptable.
// These must be at the very top of the file. Do not edit.
// icon-color: orange; icon-glyph: gas-pump;

// Widget Scriptable : prix de l'essence de stations choisies (Régie de l'énergie du Québec)
// Petit widget : prix du Régulier. Moyen/grand : Régulier, Super et Diesel.

const URL = "https://regieessencequebec.ca/stations.geojson.gz";

// Un même numéro d'entreprise peut posséder plusieurs stations : on valide aussi l'adresse.
const STATIONS = [
  { label: "Ultramar Bois-Francs", name: "9402-0195", address: "bois francs" },
  { label: "Harnois", name: "488-9037", address: "pierre-roux" },
  { label: "Couche-Tard des Roses", name: "couche-tard #1129", address: "des roses" },
];

const FUELS = [
  { key: "Régulier", short: "Rég." },
  { key: "Super", short: "Sup." },
  { key: "Diesel", short: "Dsl." },
];

const fm = FileManager.local();
const CACHE = fm.joinPath(fm.cacheDirectory(), "prix-essence-cache.json");

function norm(s) {
  return (s || "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/ /g, " ")
    .toLowerCase();
}

function parsePrice(p) {
  const n = parseFloat(String(p || "").replace(",", "."));
  return isNaN(n) ? null : n;
}

async function loadData() {
  try {
    const req = new Request(URL);
    req.timeoutInterval = 20;
    // Le serveur répond avec Content-Encoding: gzip, iOS décompresse automatiquement.
    const json = await req.loadJSON();
    const result = {
      generatedAt: json.metadata && json.metadata.generated_at,
      stations: STATIONS.map((s) => {
        const f = json.features.find((f) => {
          const p = f.properties;
          return norm(p.Name).includes(norm(s.name)) && norm(p.Address).includes(norm(s.address));
        });
        if (!f) return { label: s.label, prices: {} };
        const prices = {};
        for (const pr of f.properties.Prices || []) {
          if (pr.IsAvailable) prices[pr.GasType] = parsePrice(pr.Price);
        }
        return { label: s.label, status: f.properties.Status, prices };
      }),
    };
    fm.writeString(CACHE, JSON.stringify(result));
    return { ...result, stale: false };
  } catch (e) {
    if (fm.fileExists(CACHE)) return { ...JSON.parse(fm.readString(CACHE)), stale: true };
    throw e;
  }
}

function fmt(n) {
  return n == null ? "—" : n.toFixed(1) + "¢";
}

function buildWidget(data) {
  const family = config.widgetFamily || "medium";
  const small = family === "small";
  const fuels = small ? FUELS.slice(0, 1) : FUELS;

  const w = new ListWidget();
  const bg = new LinearGradient();
  bg.colors = [new Color("#1c1c1e"), new Color("#2c2c2e")];
  bg.locations = [0, 1];
  w.backgroundGradient = bg;
  w.setPadding(12, 12, 12, 12);
  w.refreshAfterDate = new Date(Date.now() + 30 * 60 * 1000);

  const title = w.addText(small ? "⛽ Régulier" : "⛽ Prix de l'essence");
  title.font = Font.boldSystemFont(small ? 13 : 14);
  title.textColor = Color.white();
  w.addSpacer(small ? 6 : 8);

  // Prix le plus bas par carburant, pour le mettre en vert
  const minByFuel = {};
  for (const f of fuels) {
    const vals = data.stations.map((s) => s.prices[f.key]).filter((v) => v != null);
    minByFuel[f.key] = vals.length ? Math.min(...vals) : null;
  }

  if (!small) {
    const header = w.addStack();
    header.addSpacer();
    for (const f of fuels) {
      const cell = header.addStack();
      cell.size = new Size(52, 0);
      cell.addSpacer();
      const t = cell.addText(f.short);
      t.font = Font.mediumSystemFont(11);
      t.textColor = Color.gray();
    }
    w.addSpacer(2);
  }

  for (const s of data.stations) {
    const row = w.addStack();
    row.centerAlignContent();
    const name = row.addText(s.label);
    name.font = Font.systemFont(small ? 11 : 13);
    name.textColor = Color.white();
    name.lineLimit = 1;
    name.minimumScaleFactor = 0.7;
    row.addSpacer();
    for (const f of fuels) {
      const v = s.prices[f.key];
      const cell = row.addStack();
      cell.size = new Size(small ? 48 : 52, 0);
      cell.addSpacer();
      const t = cell.addText(fmt(v));
      t.font = Font.semiboldMonospacedSystemFont(small ? 12 : 13);
      t.textColor = v != null && v === minByFuel[f.key] ? new Color("#30d158") : Color.white();
      t.minimumScaleFactor = 0.8;
      t.lineLimit = 1;
    }
    w.addSpacer(small ? 4 : 5);
  }

  w.addSpacer();
  const df = new DateFormatter();
  df.locale = "fr_CA";
  df.useShortTimeStyle();
  df.useNoDateStyle();
  const updated = data.generatedAt ? new Date(data.generatedAt) : new Date();
  const foot = w.addText((data.stale ? "⚠︎ hors ligne · " : "Maj ") + df.string(updated));
  foot.font = Font.systemFont(10);
  foot.textColor = data.stale ? Color.orange() : Color.gray();

  w.url = "https://regieessencequebec.ca/";
  return w;
}

function errorWidget(msg) {
  const w = new ListWidget();
  w.backgroundColor = new Color("#1c1c1e");
  const t = w.addText("⛽ Erreur : " + msg);
  t.font = Font.systemFont(12);
  t.textColor = Color.orange();
  return w;
}

let widget;
try {
  widget = buildWidget(await loadData());
} catch (e) {
  widget = errorWidget(String(e.message || e));
}

if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  await widget.presentMedium();
}
Script.complete();
