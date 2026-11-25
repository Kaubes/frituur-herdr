// Every visible string. Flemish, short and dry.

export const T = {
  bestellingen: "Bestellingen",
  leeg: "Nog geen volk.",
  nummer: (n) => `Nummer ${n}!`,
  nr: (n) => `NR ${n}`,
  meer: (n) => `+${n}`,
  terminalOp: "Terminal omhoog",
  terminalNeer: "Terminal omlaag",
  animAan: "Animaties: aan",
  animUit: "Animaties: uit",
  zonder: "(nog niks besteld)",
  onbekend: "(bon niet leesbaar)", // no hook: the order is unknown
};

/** The word on a bon, per fase. */
export const WOORD = {
  kiest: "kijkt naar de kaart",
  denkt: "denkt na",
  diepvries: "zoekt in de diepvries",
  bakt: "aan 't bakken",
  schudt: "schudt het mandje",
  test: "proeft even",
  olie: "ververst de olie",
  wacht: "wacht op u",
  klaar: "klaar!",
  koud: "wordt koud",
  eet: "smakelijk",
  fout: "aangebrand",
};

const ZEG = {
  wacht: ["Welke saus?", "Allez, zeg het maar.", "Met of zonder?", "Groot of klein?"],
  klaar: null,
  koud: ["Ze worden koud, hé.", "Niemand voor deze?", "Straks is 't puree."],
  fout: ["Aangebrand.", "Oei. Opnieuw.", "Dat was te lang."],
};

/** What is said above a customer for a fase, stable for a session. */
export function zeg(fase, seed) {
  const list = ZEG[fase];
  return list ? list[seed % list.length] : "";
}

/** "nu", "4 min", "2 u". */
export function sinds(ms) {
  const m = Math.floor(ms / 60000);
  return m < 1 ? "nu" : m < 60 ? `${m} min` : `${Math.floor(m / 60)} u`;
}
