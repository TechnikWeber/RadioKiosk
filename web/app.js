"use strict";

/* ---------- preferences of this display ---------- */

// Kept in the browser, not in the service: a phone used as remote control wants
// other choices than the kiosk screen.
const pref = (key, fallback) => {
  try { return localStorage.getItem(key) ?? fallback; } catch (e) { return fallback; }
};
const setPref = (key, value) => { try { localStorage.setItem(key, value); } catch (e) { /* stays default */ } };


const STRINGS = {
  en: {
    webradio: "Web radio", dab: "DAB+", fm: "FM", settings: "Settings",
    favorites: "Favorites", popular: "Popular", search: "Search", go: "Go",
    noFavorites: "No favorites yet. Tap the star next to a station.",
    noResults: "No stations found.", loading: "Loading…",
    scan: "Scan for stations", scanning: "Scanning block", found: "found",
    reception: "Reception", noSignal: "No signal",
    noServices: "No stations stored yet. Start a scan.",
    noSdr: "No RTL-SDR stick found", notInstalled: "not installed", noMpv: "mpv is not installed",
    running: "Running", quit: "Quit", expert: "Expert receiver",
    output: "Audio output", save: "Save", remove: "Remove",
    tuner: "Receiver", tunerSub: "Shortwave, 2 m, 70 cm …", squelch: "Squelch", off: "off",
    signal: "Signal", gainLabel: "Gain", stereo: "Stereo", muted: "squelched", zoom: "Zoom",
    waterfall: "Waterfall", on: "on", tooSmall: "needs more memory",
    wifiSaving: "Wi-Fi power saving",
    device: "Device", brightness: "Brightness", wifi: "Wi-Fi", wifiPassword: "Password for", connect: "Connect",
    connecting: "Connecting…", connected: "connected", update: "Update RadioKiosk", updating: "Updating…",
    upToDate: "Already up to date", updated: "Updated – restarting", restart: "Restart", shutDown: "Shut down",
    sure: "Tap again to confirm", liveStream: "Listen along on other devices (remote control must be on):",
    scanChannels: "Scan", stopScan: "Stop scan", onAir: "On the air nearby (EiBi schedule)",
    record: "Record", recordingTo: "Recording to Music/RadioKiosk",
    warn: { undervoltage: "The power supply is too weak: reception suffers and the SDR stick may hang." },
    adsb: "Aircraft", adsbSub: "Live map (ADS-B)", aircraftSeen: "aircraft received", withPosition: "with position",
    weather: "Weather", wind: "Wind", rain: "Rain", today: "Today",
    needLocation: "Set your location first: Settings → Location.",
    location: "Location", locationHint: "Move the map until the cross marks your place.", locationSave: "Use this place",
    locationSet: "set", locationUnset: "not set", sleepTimer: "Sleep timer", minutes: "min",
    language: "Language", languages: { en: "English", de: "Deutsch" },
    manage: "Manage favorites", clearAll: "Remove all", clearSure: "Really remove all?",
    kinds2: { webradio: "Web radio", dab: "DAB+", fm: "FM", tuner: "Receiver" },
    list: "List", remote: "Remote control", remoteOn: "on", remoteHint: "Phones and computers in your network can now open:",
    remoteWarning: "There is no password: everyone in this network can operate the radio.",
    alarm: "Alarm", alarmOn: "Alarm is on", alarmOff: "Alarm is off", wakesWith: "Wakes with",
    wakesWithNothing: "Play a station once; the alarm can then wake with it.",
    wakeLast: "Station heard last", wakeFixed: "Always", wakeFix: "Always wake with",
    sound: "Sound", soundModes: { auto: "Auto", stereo: "Stereo", mono: "Mono" },
    gallery: "Gallery", gallerySub: "Slide show", gallerySetup: "Set up the gallery", chooseFolder: "Choose folder",
    galleryIntro: "Shows the pictures of a folder as a slide show: without anything on top through the Gallery tile, and behind the clock where the idle screen is set to show the gallery.",
    galleryNetwork: "A USB stick or a network folder can be chosen once this computer has mounted it.",
    galleryUnset: "No folder chosen yet.", galleryEmpty: "There are no pictures in the chosen folder.",
    folderMissing: "folder not found – stick or network folder missing?", pictures: "pictures",
    slideTime: "Change every", shuffle: "Shuffle", galleryIdle: "On the idle screen",
    takeFolder: "Use this folder", picturesHere: "pictures directly in it",
    podcasts: "Podcasts", subscriptions: "Subscribed", noSubscriptions: "No podcasts subscribed yet. Find one under Search.",
    subscribe: "Subscribe", subscribedOn: "Subscribed", noEpisodes: "This podcast has no episodes to play.", heardTo: "heard to",
    podcastDirectory: "Podcast directory", directories: { fyyd: "fyyd", apple: "Apple Podcasts", podcastindex: "Podcast Index" },
    directoryHint: "Where the search looks for podcasts. fyyd and Apple work without a key; the Podcast Index is free as well, but needs a key and a secret from podcastindex.org.",
    apiKey: "Key", apiSecret: "Secret", notSet: "not set", isSet: "set",
    news: "News", newsSub: "RSS reader", manageFeeds: "News feeds", addFeed: "Add feed", feedAddress: "Address of the feed (RSS or Atom)",
    noArticles: "No articles yet.", noFeeds: "No feed chosen yet. Tap a suggestion, or add your own under News feeds.", remove: "Remove",
    sensors: "Sensors", sensorsSub: "433 MHz", sensorsWaiting: "Listening for wireless sensors … many only report every few minutes.",
    sensorWords: { humidity: "humidity", battery: "battery low", wind: "wind", rain: "rain", ago: "ago", channel: "channel" },
    ais: "Ships", aisSub: "Live map (AIS)", shipsSeen: "ships received",
    timer: "Timer", timerSub: "and stopwatch", stopwatch: "Stopwatch", start: "Start", stopIt: "Stop", reset: "Reset", cancel: "Cancel",
    timeUp: "Time is up",
    idleContent: "Shows", idleContents: { clock: "clock", gallery: "gallery", feed: "news" },
    galleryFit: "Pictures", galleryFits: { whole: "whole picture", smart: "zoom slightly", fill: "fill the screen" },
    subfoldersToo: "Subfolders", demoPictures: "Demo pictures (no folder of your own chosen yet)",
    sectionPlayback: "Playback", sectionDisplay: "Display", sectionContent: "Content", sectionReception: "Reception",
    sectionDevice: "Device and network", idleAfter: "Starts after",
    suggestions: "Suggestions", tiles: "Tiles on the start screen", tilesHint: "Tap a tile to hide it or bring it back.",
    shown: "shown", hiddenTile: "hidden",
    theme: "Design", themes: { dark: "dark", light: "light" },
    bar: "Bottom bar", barSizes: { small: "small", medium: "medium", large: "large" },
    idle: "Idle screen", keyboard: "On-screen keyboard", keyboardModes: { auto: "auto", on: "on", off: "off" },
    bluetooth: "Bluetooth", btSub: "Speakers and phone", btVisible: "Let a phone connect", btVisibleFor: "Visible for",
    btPhoneHint: "Then pick this device in the phone's Bluetooth settings and play music.",
    btScan: "Search for speakers", btScanning: "Searching…", btConnected: "connected", btPaired: "paired", btNew: "new",
    seconds: "s",
    version: "Version", receiverSetting: "How FM and the receiver listen",
    receiverIntro: "The SDR stick only delivers raw radio data. A program on this computer turns it into sound. RadioKiosk has two of them:",
    engineName: "Own receiver", engineSub: "built into RadioKiosk",
    enginePoints: ["+stereo", "+station name and radio text (RDS)", "+waterfall", "+retunes without a gap", "-needs more processing power"],
    rtlName: "rtl_fm", rtlSub: "classic program from the rtl-sdr package",
    rtlPoints: ["-mono", "-no station name, no radio text", "-no waterfall", "-short gap on every retune", "+light on the processor"],
    loadNow: "On this computer the own receiver needs {n} % of one processor core.",
    loadRule: "Automatic picks it up to {n} % (the mark) and rtl_fm above that.",
    loadNone: "The own receiver cannot run here (NumPy or the stick's library is missing), so rtl_fm is used.",
    runsWith: "runs with", choiceAuto: "Automatic",
    wmo: { 0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 51: "Drizzle", 61: "Rain",
           66: "Freezing rain", 71: "Snow", 80: "Showers", 85: "Snow showers", 95: "Thunderstorm" },
    fmScanning: "Scanning the band…", fmFound: "Found", fmSaved: "Saved",
    enterFrequency: "Up to 1750: MHz · from 2000: kHz", cancel: "Cancel",
    relevel: "Reset remembered gain",
    relevelHint: "The tuner gain adjusts itself and is remembered per band. Reset it after changing the antenna or location.",
    kinds: { analog: "Headphone jack / built-in", usb: "USB", bluetooth: "Bluetooth", hdmi: "HDMI" },
  },
  de: {
    webradio: "Webradio", dab: "DAB+", fm: "UKW", settings: "Einstellungen",
    favorites: "Favoriten", popular: "Beliebt", search: "Suche", go: "Los",
    noFavorites: "Noch keine Favoriten. Tippe auf den Stern neben einem Sender.",
    noResults: "Keine Sender gefunden.", loading: "Lädt…",
    scan: "Sendersuchlauf", scanning: "Suche in Block", found: "gefunden",
    reception: "Empfang", noSignal: "Kein Signal",
    noServices: "Noch keine Sender gespeichert. Starte einen Suchlauf.",
    noSdr: "Kein RTL-SDR-Stick gefunden", notInstalled: "nicht installiert", noMpv: "mpv ist nicht installiert",
    running: "Läuft", quit: "Beenden", expert: "Experten-Empfänger",
    output: "Tonausgabe", save: "Speichern", remove: "Entfernen",
    tuner: "Empfänger", tunerSub: "Kurzwelle, 2 m, 70 cm …", squelch: "Rauschsperre", off: "aus",
    signal: "Signal", gainLabel: "Verstärkung", stereo: "Stereo", muted: "Rauschsperre zu", zoom: "Zoom",
    waterfall: "Wasserfall", on: "an", tooSmall: "braucht mehr Arbeitsspeicher",
    wifiSaving: "WLAN-Stromsparen",
    device: "Gerät", brightness: "Helligkeit", wifi: "WLAN", wifiPassword: "Passwort für", connect: "Verbinden",
    connecting: "Verbinde…", connected: "verbunden", update: "RadioKiosk aktualisieren", updating: "Aktualisiere…",
    upToDate: "Bereits aktuell", updated: "Aktualisiert – starte neu", restart: "Neu starten", shutDown: "Ausschalten",
    sure: "Zum Bestätigen noch einmal tippen", liveStream: "Auf anderen Geräten mithören (Fernbedienung muss an sein):",
    scanChannels: "Suchlauf", stopScan: "Suchlauf stoppen", onAir: "Gerade in der Nähe auf Sendung (EiBi-Fahrplan)",
    record: "Aufnehmen", recordingTo: "Aufnahme läuft nach Musik/RadioKiosk",
    warn: { undervoltage: "Das Netzteil ist zu schwach: Der Empfang leidet und der SDR-Stick kann sich aufhängen." },
    adsb: "Flugzeuge", adsbSub: "Live-Karte (ADS-B)", aircraftSeen: "Flugzeuge empfangen", withPosition: "mit Position",
    weather: "Wetter", wind: "Wind", rain: "Regen", today: "Heute",
    needLocation: "Lege zuerst deinen Standort fest: Einstellungen → Standort.",
    location: "Standort", locationHint: "Verschiebe die Karte, bis das Kreuz auf deinem Ort liegt.", locationSave: "Diesen Ort übernehmen",
    locationSet: "festgelegt", locationUnset: "nicht festgelegt", sleepTimer: "Sleep-Timer", minutes: "min",
    language: "Sprache", languages: { en: "English", de: "Deutsch" },
    manage: "Favoriten verwalten", clearAll: "Alle entfernen", clearSure: "Wirklich alle entfernen?",
    kinds2: { webradio: "Webradio", dab: "DAB+", fm: "UKW", tuner: "Empfänger" },
    list: "Liste", remote: "Fernbedienung", remoteOn: "an", remoteHint: "Handys und Rechner in deinem Netz können jetzt öffnen:",
    remoteWarning: "Es gibt kein Passwort: Jeder in diesem Netz kann das Radio bedienen.",
    alarm: "Wecker", alarmOn: "Wecker ist an", alarmOff: "Wecker ist aus", wakesWith: "Weckt mit",
    wakesWithNothing: "Spiele einmal einen Sender; danach kann der Wecker damit wecken.",
    wakeLast: "Zuletzt gehörter Sender", wakeFixed: "Immer", wakeFix: "Immer wecken mit",
    sound: "Ton", soundModes: { auto: "Auto", stereo: "Stereo", mono: "Mono" },
    gallery: "Galerie", gallerySub: "Diashow", gallerySetup: "Galerie einrichten", chooseFolder: "Ordner wählen",
    galleryIntro: "Zeigt die Bilder eines Ordners als Diashow: über die Kachel Galerie ohne alles darüber, und hinter der Uhr, wenn der Ruhebildschirm auf Galerie gestellt ist.",
    galleryNetwork: "Ein USB-Stick oder ein Netzwerkordner lässt sich wählen, sobald dieser Rechner ihn eingebunden hat.",
    galleryUnset: "Noch kein Ordner gewählt.", galleryEmpty: "Im gewählten Ordner liegen keine Bilder.",
    folderMissing: "Ordner nicht gefunden – fehlt der Stick oder der Netzwerkordner?", pictures: "Bilder",
    slideTime: "Wechsel alle", shuffle: "Zufällige Reihenfolge", galleryIdle: "Im Ruhebildschirm",
    takeFolder: "Diesen Ordner nehmen", picturesHere: "Bilder direkt darin",
    podcasts: "Podcasts", subscriptions: "Abonniert", noSubscriptions: "Noch kein Podcast abonniert. Unter Suche findest du welche.",
    subscribe: "Abonnieren", subscribedOn: "Abonniert", noEpisodes: "Dieser Podcast hat keine abspielbaren Folgen.", heardTo: "gehört bis",
    podcastDirectory: "Podcast-Verzeichnis", directories: { fyyd: "fyyd", apple: "Apple Podcasts", podcastindex: "Podcast Index" },
    directoryHint: "Wo die Suche nach Podcasts schaut. fyyd und Apple gehen ohne Schlüssel; der Podcast Index ist ebenfalls kostenlos, braucht aber Schlüssel und Geheimnis von podcastindex.org.",
    apiKey: "Schlüssel", apiSecret: "Geheimnis", notSet: "nicht eingetragen", isSet: "eingetragen",
    news: "Nachrichten", newsSub: "RSS-Reader", manageFeeds: "Nachrichten-Feeds", addFeed: "Feed hinzufügen", feedAddress: "Adresse des Feeds (RSS oder Atom)",
    noArticles: "Noch keine Artikel.", noFeeds: "Noch kein Feed gewählt. Tippe einen Vorschlag an oder trage unter Nachrichten-Feeds einen eigenen ein.", remove: "Entfernen",
    sensors: "Funksensoren", sensorsSub: "433 MHz", sensorsWaiting: "Lausche auf Funksensoren … viele melden sich nur alle paar Minuten.",
    sensorWords: { humidity: "Feuchte", battery: "Batterie schwach", wind: "Wind", rain: "Regen", ago: "vor", channel: "Kanal" },
    ais: "Schiffe", aisSub: "Live-Karte (AIS)", shipsSeen: "Schiffe empfangen",
    timer: "Timer", timerSub: "und Stoppuhr", stopwatch: "Stoppuhr", start: "Start", stopIt: "Stopp", reset: "Zurücksetzen", cancel: "Abbrechen",
    timeUp: "Die Zeit ist um",
    idleContent: "Zeigt", idleContents: { clock: "Uhr", gallery: "Galerie", feed: "Nachrichten" },
    galleryFit: "Bilder", galleryFits: { whole: "ganzes Bild", smart: "leicht zoomen", fill: "Bildschirm füllen" },
    subfoldersToo: "Unterordner", demoPictures: "Demobilder (noch kein eigener Ordner gewählt)",
    sectionPlayback: "Wiedergabe", sectionDisplay: "Anzeige", sectionContent: "Inhalte", sectionReception: "Empfang",
    sectionDevice: "Gerät und Netz", idleAfter: "Beginnt nach",
    suggestions: "Vorschläge", tiles: "Kacheln auf dem Startbildschirm", tilesHint: "Tippe eine Kachel an, um sie auszublenden oder zurückzuholen.",
    shown: "sichtbar", hiddenTile: "ausgeblendet",
    theme: "Design", themes: { dark: "dunkel", light: "hell" },
    bar: "Untere Leiste", barSizes: { small: "klein", medium: "mittel", large: "groß" },
    idle: "Ruhebildschirm", keyboard: "Bildschirmtastatur", keyboardModes: { auto: "automatisch", on: "an", off: "aus" },
    bluetooth: "Bluetooth", btSub: "Lautsprecher und Handy", btVisible: "Handy verbinden lassen", btVisibleFor: "Sichtbar für",
    btPhoneHint: "Wähle danach dieses Gerät in den Bluetooth-Einstellungen des Handys und spiele Musik ab.",
    btScan: "Lautsprecher suchen", btScanning: "Suche…", btConnected: "verbunden", btPaired: "gekoppelt", btNew: "neu",
    seconds: "s",
    version: "Version", receiverSetting: "Womit UKW und Empfänger hören",
    receiverIntro: "Der SDR-Stick liefert nur rohe Funkdaten. Ein Programm auf diesem Rechner macht daraus Ton. RadioKiosk hat zwei davon:",
    engineName: "Eigener Empfänger", engineSub: "in RadioKiosk eingebaut",
    enginePoints: ["+Stereo", "+Sendername und Radiotext (RDS)", "+Wasserfall", "+stimmt ohne Pause um", "-braucht mehr Rechenleistung"],
    rtlName: "rtl_fm", rtlSub: "klassisches Programm aus dem rtl-sdr-Paket",
    rtlPoints: ["-Mono", "-kein Sendername, kein Radiotext", "-kein Wasserfall", "-kurze Pause bei jedem Umstimmen", "+schont den Prozessor"],
    loadNow: "Auf diesem Rechner braucht der eigene Empfänger {n} % eines Prozessorkerns.",
    loadRule: "Automatisch nimmt ihn bis {n} % (die Marke), darüber rtl_fm.",
    loadNone: "Der eigene Empfänger kann hier nicht laufen (NumPy oder die Bibliothek des Sticks fehlt), deshalb läuft rtl_fm.",
    runsWith: "läuft mit", choiceAuto: "Automatisch",
    wmo: { 0: "Klar", 1: "Überwiegend klar", 2: "Teils bewölkt", 3: "Bedeckt", 45: "Nebel", 51: "Nieselregen", 61: "Regen",
           66: "Gefrierender Regen", 71: "Schnee", 80: "Schauer", 85: "Schneeschauer", 95: "Gewitter" },
    fmScanning: "Suche Sender im Band…", fmFound: "Gefunden", fmSaved: "Gespeichert",
    enterFrequency: "Bis 1750: MHz · ab 2000: kHz", cancel: "Abbrechen",
    relevel: "Gemerkte Verstärkung zurücksetzen",
    relevelHint: "Die Verstärkung regelt sich selbst und wird je Band gemerkt. Nach Antennen- oder Standortwechsel zurücksetzen.",
    kinds: { analog: "Klinke / eingebaut", usb: "USB", bluetooth: "Bluetooth", hdmi: "HDMI" },
  },
};
// English unless switched under Settings
const lang = STRINGS[pref("lang", "en")] ? pref("lang", "en") : "en";
const t = STRINGS[lang];

// The service reports problems in English; these are their German counterparts.
const MESSAGES_DE = [
  [/^the SDR stick hung and was restarted.*$/, "Der SDR-Stick hing und wurde neu gestartet – bitte noch einmal versuchen"],
  [/^the SDR stick does not respond$/, "Der SDR-Stick reagiert nicht"],
  [/^nothing is playing$/, "Es läuft gerade nichts"],
  [/^the scan needs the own receiver$/, "Der Suchlauf braucht den eigenen Empfänger"],
  [/^could not connect to this network.*$/, "Verbindung mit diesem Netz fehlgeschlagen – falsches Passwort?"],
  [/^update failed.*$/, "Aktualisierung fehlgeschlagen – besteht eine Internetverbindung?"],
  [/^this computer has too little memory for that program$/, "Dieser Rechner hat zu wenig Arbeitsspeicher für dieses Programm"],
  [/^no data from the SDR stick.*$/, "Der SDR-Stick liefert keine Daten – falls das anhält, neu einstecken"],
  [/^cannot open the SDR stick.*$/, "Der SDR-Stick lässt sich nicht öffnen – nutzt ihn ein anderes Programm?"],
  [/^the SDR stick stopped delivering data.*$/, "Der SDR-Stick liefert keine Daten mehr – bitte neu einstecken"],
  [/^the receiver stopped unexpectedly$/, "Der Empfänger wurde unerwartet beendet"],
  [/^weak reception \(SNR (.+) dB\)$/, "Schwacher Empfang (Signalabstand $1 dB)"],
  [/^reception on block (.+) is too weak$/, "Der Empfang auf Block $1 ist zu schwach"],
  [/^this computer does not let RadioKiosk change that setting$/, "Dieser Rechner lässt RadioKiosk diese Einstellung nicht ändern"],
  [/^no Wi-Fi connection$/, "Keine WLAN-Verbindung"],
  [/^this folder cannot be opened$/, "Dieser Ordner lässt sich nicht öffnen"],
  [/^no reception on block (.+)$/, "Kein Empfang auf Block $1"],
  [/^welle-cli could not open the SDR$/, "welle-cli konnte den SDR-Stick nicht öffnen"],
  [/^welle-cli did not start$/, "welle-cli ist nicht gestartet"],
  [/^the player \(mpv\) did not start$/, "Der Abspieler (mpv) ist nicht gestartet"],
  [/^the player \(mpv\) is not running$/, "Der Abspieler (mpv) läuft nicht"],
  [/^podcast directory unreachable$/, "Das Podcast-Verzeichnis ist nicht erreichbar"],
  [/^the podcast directory refused the key$/, "Das Podcast-Verzeichnis hat den Schlüssel abgelehnt"],
  [/^the Podcast Index needs a key and a secret$/, "Der Podcast Index braucht Schlüssel und Geheimnis (Einstellungen › Podcast-Verzeichnis)"],
  [/^this feed cannot be reached$/, "Dieser Feed ist nicht erreichbar"],
  [/^this address does not deliver a feed$/, "Unter dieser Adresse gibt es keinen Feed"],
  [/^rtl_433 could not open the SDR stick$/, "rtl_433 konnte den SDR-Stick nicht öffnen"],
  [/^rtl_ais could not open the SDR stick$/, "rtl_ais konnte den SDR-Stick nicht öffnen"],
  [/^unknown service$/, "Dieser Sender ist nicht mehr in der Liste – bitte den Suchlauf neu starten"],
  [/^station directory unreachable.*$/, "Das Senderverzeichnis ist nicht erreichbar"],
  [/^weather service unreachable.*$/, "Der Wetterdienst ist nicht erreichbar"],
  [/^the ADS-B decoder could not open the SDR stick$/, "Der ADS-B-Dekoder konnte den SDR-Stick nicht öffnen"],
  [/^the ADS-B decoder stopped unexpectedly$/, "Der ADS-B-Dekoder wurde unerwartet beendet"],
  [/^no ADS-B decoder installed$/, "Kein ADS-B-Dekoder installiert"],
  [/^could not connect.*$/, "Verbindung fehlgeschlagen – ist das Gerät im Kopplungsmodus?"],
  [/^nothing has been played yet$/, "Es wurde noch nichts abgespielt"],
  [/^scan timed out$/, "Der Suchlauf hat zu lange gedauert"],
  [/^mpv is not installed$/, "mpv ist nicht installiert"],
  [/^(playback|loading) failed$/, "Die Wiedergabe ist fehlgeschlagen"],
  [/^unrecognized file format$/, "Der Sender liefert kein abspielbares Format"],
];
const say = text => {
  if (lang !== "de" || !text) return text;
  const match = MESSAGES_DE.find(([pattern]) => pattern.test(text));
  return match ? text.replace(match[0], match[1]) : text;
};
document.documentElement.lang = lang;
// band plan entries carry their names as plain text or as { de, en }
const tr = name => typeof name === "string" ? name : name[lang] || name.en;

const ICONS = {
  webradio: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
  dab: '<rect x="3" y="8" width="18" height="12" rx="2"/><path d="M7 8l9-5M7 14h4M16 14h.01M7 17h4"/>',
  fm: '<path d="M12 12v9M8 16a5.5 5.5 0 010-8M16 8a5.5 5.5 0 010 8M5 19a10 10 0 010-14M19 5a10 10 0 010 14"/>',
  app: '<path d="M3 17l4-9 3 6 3-10 3 8 2-3 3 8"/>',
  tuner: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2"/><path d="M12 3v3M12 10V7M5.6 5.6l2 2M3 12h3M18.4 5.6l-2 2M21 12h-3"/>',
  adsb: '<path d="M12 3l2 7 7 4v2l-7-2v4l2 2v1l-4-1-4 1v-1l2-2v-4l-7 2v-2l7-4z"/>',
  podcast: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3"/>',
  news: '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 9h8M8 13h8M8 17h5"/>',
  sensors: '<path d="M10 14V5a2 2 0 014 0v9a4 4 0 11-4 0z"/><path d="M12 17v-6"/>',
  ais: '<path d="M3 17l2 4h14l2-4M5 17v-6h14v6M9 11V6h6v5M12 6V3"/>',
  timer: '<circle cx="12" cy="13" r="8"/><path d="M12 13V9M9 2h6"/>',
  gallery: '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="8.5" cy="10" r="1.5"/><path d="M21 16l-5-5-8 8"/>',
  weather: '<circle cx="8" cy="8" r="3"/><path d="M8 2v1M2 8h1M3.8 3.8l.7.7M12.2 3.8l-.7.7M8 20h9a4 4 0 000-8 6 6 0 00-11 2 3 3 0 002 6z"/>',
  bluetooth: '<path d="M7 7l10 10-5 4V3l5 4L7 17"/>',
  settings: '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
  star: '<path d="M12 4l2.5 5.2 5.5.8-4 4 1 5.6-5-2.7-5 2.7 1-5.6-4-4 5.5-.8z"/>',
};
const icon = name => `<svg viewBox="0 0 24 24">${ICONS[name]}</svg>`;

const $ = id => document.getElementById(id);
const view = $("view");
let state = { caps: { apps: [] }, detail: {}, backends: {}, warnings: [] };
let current = null;   // the visible view: { title, render(), onState?() }

function h(tag, props = {}, ...children) {
  const el = Object.assign(document.createElement(tag), props);
  el.append(...children.filter(c => c != null));
  return el;
}

async function api(path, body) {
  // the service looks up place names in the language of the interface
  const response = await fetch(path, body === undefined ? { headers: { "Accept-Language": lang } } : {
    method: "POST", headers: { "Content-Type": "application/json", "Accept-Language": lang }, body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

function show(v) {
  if (current && current.leave) current.leave();
  current = v;
  $("heading").textContent = v.title;
  $("version").hidden = v !== home;
  $("back").hidden = v === home;
  view.scrollTop = 0;
  v.render();
}

const hint = text => h("p", { className: "hint", textContent: text });

function stationRow({ title, info, active, onPlay, starred, onStar, logo }) {
  const picture = logo ? h("img", { className: "logo", src: logo, loading: "lazy", alt: "" }) : null;
  if (picture) picture.onerror = () => picture.remove();   // many stations list a logo that no longer exists
  const row = h("div", { className: "row" + (active ? " current" : "") },
    h("button", { onclick: onPlay }, picture,
      h("span", { className: "texts" }, h("b", { textContent: title }), h("small", { textContent: info || "" }))));
  if (onStar) {
    row.append(h("button", { className: "icon star" + (starred ? " on" : ""), innerHTML: icon("star"), onclick: onStar }));
  }
  return row;
}

/* ---------- favorites ---------- */

// One list for all sources; an entry carries what its source needs to play it.
let favorites = [];
const favKey = e => `${e.kind}|` + {
  webradio: () => e.station.id, dab: () => e.sid, fm: () => Number(e.mhz).toFixed(2), tuner: () => `${e.hz}/${e.mode}`,
}[e.kind]();
const isStarred = entry => favorites.some(f => favKey(f) === favKey(entry));
async function toggleStar(entry) {
  favorites = await api("/api/favorites", entry);
  current.draw();
}

const favoritesView = {
  title: t.favorites,
  sure: false,
  render() { this.sure = false; this.draw(); },
  draw() {
    view.replaceChildren(
      ...(favorites.length ? [] : [hint(t.noFavorites)]),
      ...favorites.map(f => stationRow({
        title: f.title, info: t.kinds2[f.kind], starred: true,
        onPlay: () => api("/api/favorites/play", f), onStar: () => toggleStar(f),
      })),
      ...(favorites.length ? [h("div", { className: "toolbar" }, h("button", {
        textContent: this.sure ? t.clearSure : t.clearAll,
        onclick: async () => {
          if (this.sure) favorites = await api("/api/favorites/clear", {});
          this.sure = !this.sure;
          this.draw();
        },
      }))] : []));
  },
};

/* ---------- on-screen keyboard ---------- */

// Every desktop brings a different on-screen keyboard, or none in kiosk mode, so the
// interface has its own. "auto" shows it on touch screens; where the system keyboard
// works well, switch it off under Settings.
// "auto" goes by what touched the screen last: a finger gets the keyboard, a mouse does not.
// Asking the browser for a "coarse pointer" is not enough; a touch screen on a desktop
// that also offers a mouse pointer answers no.
let lastPointer = matchMedia("(pointer: coarse)").matches ? "touch" : "mouse";
addEventListener("pointerdown", e => { lastPointer = e.pointerType; }, true);
const keyboardWanted = () => {
  const mode = pref("keyboard", "auto");
  return mode === "on" || (mode === "auto" && lastPointer !== "mouse");
};

const KEYS = {
  de: ["qwertzuiopü", "asdfghjklöä", "yxcvbnmß"],
  en: ["qwertyuiop", "asdfghjkl", "zxcvbnm"],
  numbers: ["1234567890", "-/:;()&@+", ".,?!'\"#_=~%"],
};

function keyboard(input, onEnter) {
  let shift = false, numbers = false;
  const el = h("div", { className: "keys" });
  const set = value => { input.value = value; input.dispatchEvent(new Event("input")); };
  const draw = () => {
    const key = (label, action, className = "") => h("button", {
      className, textContent: label, onclick: () => { action(); draw(); },
    });
    const letter = ch => {
      const out = shift ? ch.toUpperCase() : ch;
      return key(out, () => { set(input.value + out); shift = false; });
    };
    const rows = numbers ? KEYS.numbers : KEYS[lang];
    el.replaceChildren(
      h("div", { className: "key-row" }, ...[...rows[0]].map(letter)),
      h("div", { className: "key-row" }, ...[...rows[1]].map(letter)),
      h("div", { className: "key-row" },
        key("⇧", () => { shift = !shift; }, shift ? "wide on" : "wide"),
        ...[...rows[2]].map(letter),
        key("⌫", () => set(input.value.slice(0, -1)), "wide")),
      h("div", { className: "key-row" },
        key(numbers ? "abc" : "123", () => { numbers = !numbers; }, "wide"),
        key(" ", () => set(input.value + " "), "space"),
        key("OK", onEnter, "primary wide")));
  };
  draw();
  return el;
}

/* ---------- spectrum and waterfall ---------- */

const PALETTE = (() => {
  // dark blue -> cyan -> yellow -> white
  const stops = [[0, 8, 12, 40], [0.35, 20, 90, 170], [0.6, 40, 200, 200], [0.8, 250, 220, 80], [1, 255, 255, 255]];
  const colors = new Uint8ClampedArray(256 * 4);
  for (let i = 0; i < 256; i++) {
    const x = i / 255;
    const k = stops.findIndex(stop => stop[0] >= x) || 1;
    const [a, b] = [stops[k - 1], stops[k]];
    const f = (x - a[0]) / (b[0] - a[0]);
    for (let c = 0; c < 3; c++) colors[i * 4 + c] = a[c + 1] + (b[c + 1] - a[c + 1]) * f;
    colors[i * 4 + 3] = 255;
  }
  return colors;
})();

// One spectrum line from the receiver engine: header, then one byte per point (0..255 = -120..0 dBFS).
function parseSpectrum(buffer) {
  const head = new DataView(buffer);
  const flags = head.getUint8(36);
  return {
    start: head.getFloat64(0, true), span: head.getFloat64(8, true), tuned: head.getFloat64(16, true),
    snr: head.getFloat32(28, true), gain: head.getFloat32(32, true),
    stereo: !!(flags & 1), squelched: !!(flags & 2), line: new Uint8Array(buffer, 37),
  };
}

const meterText = s => [
  `${t.signal} ${Math.max(0, s.snr).toFixed(0)} dB`, `${t.gainLabel} ${s.gain.toFixed(0)} dB`,
  s.stereo ? t.stereo : null, s.squelched ? t.muted : null,
].filter(Boolean).join(" · ");

// The waterfall is off unless switched on, separately for each tile: for listening to
// the radio it is a distraction, for hunting signals it is the point.
const waterfallOn = tile => pref(`waterfall_${tile}`, "off") === "on";
const waterfallButton = (tile, redraw) => state.backends[tile] !== "engine" ? null : h("button", {
  className: waterfallOn(tile) ? "on" : "",
  textContent: `${t.waterfall}: ${waterfallOn(tile) ? t.on : t.off}`,
  onclick: () => { setPref(`waterfall_${tile}`, waterfallOn(tile) ? "off" : "on"); redraw(); },
});

// Spectrum trace on top, waterfall below. The element keeps its picture while views redraw around it.
function makeWaterfall(onTune) {
  const TRACE = 48, ROWS = 72;
  const canvas = h("canvas", { className: "waterfall", width: 1024, height: TRACE + ROWS });
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  const row = ctx.createImageData(1024, 1);
  let last = null, floor = 60;
  canvas.onclick = e => {
    if (!last) return;
    const box = canvas.getBoundingClientRect();
    onTune(last.start + (e.clientX - box.left) / box.width * last.span);
  };
  return {
    el: canvas,
    push(s) {
      if (!last || last.start !== s.start || last.span !== s.span) ctx.clearRect(0, 0, 1024, TRACE + ROWS);
      last = s;
      // follow the noise floor so the colours fit weak and strong bands alike
      const sorted = Uint8Array.from(s.line).sort();
      floor += (sorted[300] - floor) * 0.1;
      const scale = v => Math.min(1, Math.max(0, (v - floor + 6) / 110));   // about 50 dB of range
      ctx.drawImage(canvas, 0, TRACE, 1024, ROWS - 1, 0, TRACE + 1, 1024, ROWS - 1);
      for (let x = 0; x < 1024; x++) {
        row.data.set(PALETTE.subarray(Math.round(scale(s.line[x]) * 255) * 4, Math.round(scale(s.line[x]) * 255) * 4 + 4), x * 4);
      }
      ctx.putImageData(row, 0, TRACE);
      ctx.clearRect(0, 0, 1024, TRACE);
      ctx.beginPath();
      for (let x = 0; x < 1024; x++) ctx.lineTo(x, TRACE - 2 - scale(s.line[x]) * (TRACE - 4));
      ctx.strokeStyle = "#93a1b3";
      ctx.lineWidth = 1.5;
      ctx.stroke();
      const marker = (s.tuned - s.start) / s.span * 1024;
      ctx.fillStyle = "#ffb347";
      ctx.fillRect(marker - 1, 0, 2, TRACE);
    },
  };
}

/* ---------- home ---------- */

const home = {
  title: "RadioKiosk",
  render() {
    const c = state.caps;
    const sdrProblem = !c.sdr ? t.noSdr : null;
    const tile = (id, label, problem, onclick, sub) => {
      const el = h("button", {
        className: "tile" + (state.source === id ? " running" : ""), disabled: !!problem, onclick,
        innerHTML: icon(id) + `<span>${label}</span>` + (problem || sub ? `<small>${problem || sub}</small>` : ""),
      });
      el.dataset.tile = id;
      return el;
    };
    const hidden = state.hidden_tiles || [];
    const favorite = f => h("button", { onclick: () => api("/api/favorites/play", f) },
      h("i", { innerHTML: icon(f.kind) }), h("span", { textContent: f.title }));
    view.replaceChildren(
      ...(favorites.length ? [h("div", { className: "favrow" }, ...favorites.map(favorite),
        h("button", { className: "icon", innerHTML: icon("star"), ariaLabel: t.manage, onclick: () => show(favoritesView) }))] : []),
      h("div", { className: "tiles" }, ...[
      tile("webradio", t.webradio, c.mpv ? null : t.noMpv, () => show(webradio)),
      tile("dab", t.dab, c.dab ? sdrProblem : `welle-cli ${t.notInstalled}`, () => show(dab)),
      tile("fm", t.fm, c.fm ? sdrProblem : `librtlsdr ${t.notInstalled}`, () => show(fm)),
      tile("tuner", t.tuner, c.fm ? sdrProblem : `librtlsdr ${t.notInstalled}`, () => show(tuner), t.tunerSub),
      tile("adsb", t.adsb, c.adsb ? sdrProblem : `dump1090 ${t.notInstalled}`, () => show(adsb), t.adsbSub),
      ...c.apps.map(a => {
        const running = state.source === "app" && state.detail.app === a.id;
        const el = tile("app", a.name,
          !a.available ? t.notInstalled : a.too_small ? t.tooSmall : a.needs_sdr ? sdrProblem : null,
          () => running ? api("/api/stop", {}) : api(`/api/apps/${a.id}/start`, {}),
          running ? `${t.running} – ${t.quit}` : t.expert);
        el.classList.toggle("running", running);
        el.dataset.tile = a.id;
        return el;
      }),
      ...(c.bluetooth ? [tile("bluetooth", t.bluetooth, null, () => show(bluetooth), t.btSub)] : []),
      tile("podcast", t.podcasts, c.mpv ? null : t.noMpv, () => show(podcasts)),
      tile("news", t.news, null, () => show(news), t.newsSub),
      tile("sensors", t.sensors, c.sensors ? sdrProblem : `rtl_433 ${t.notInstalled}`, () => show(sensors), t.sensorsSub),
      tile("ais", t.ais, c.ais ? sdrProblem : `rtl_ais ${t.notInstalled}`, () => show(ships), t.aisSub),
      tile("weather", t.weather, null, () => show(weather)),
      tile("gallery", t.gallery, null, () => show(galleryView), t.gallerySub),
      tile("timer", t.timer, null, () => show(timerView), t.timerSub),
      tile("settings", t.settings, null, () => show(settings)),
      ].filter(el => !hidden.includes(el.dataset.tile))));
  },
  draw() { this.render(); },
  onState() { this.render(); },
};

/* ---------- web radio ---------- */

const webradio = {
  title: t.webradio,
  tab: "favorites",
  typing: false,
  results: [],
  query: "",
  async render() {
    if (!this.starred().length && this.tab === "favorites") this.tab = "popular";
    this.draw();
    if (this.tab === "popular") this.load("");
  },
  starred() { return favorites.filter(f => f.kind === "webradio").map(f => f.station); },
  async load(query) {
    this.results = null;
    this.draw();
    try {
      this.results = await api("/api/webradio/stations?q=" + encodeURIComponent(query));
    } catch (e) {
      this.results = [];
      this.error = e.message;
    }
    if (current === this) this.draw();
  },
  draw() {
    const tabButton = id => h("button", {
      className: this.tab === id ? "on" : "", textContent: t[id],
      onclick: () => {
        Object.assign(this, { tab: id, results: [], error: null, typing: id === "search" });
        this.draw();
        if (id === "popular") this.load("");
      },
    });
    const parts = [h("div", { className: "tabs" }, tabButton("favorites"), tabButton("popular"), tabButton("search"))];
    if (this.tab === "search") {
      const input = h("input", { type: "search", value: this.query, placeholder: t.search, enterKeyHint: "search" });
      const run = () => { this.query = input.value.trim(); this.typing = false; if (this.query) this.load(this.query); else this.draw(); };
      input.oninput = () => { this.query = input.value; };
      input.onkeydown = e => { if (e.key === "Enter") run(); };
      parts.push(h("div", { className: "toolbar" }, input, h("button", { className: "primary", textContent: t.go, onclick: run })));
      if (keyboardWanted()) {
        if (this.typing) {
          input.inputMode = "none";   // keep the system keyboard away while ours is open
          view.replaceChildren(...parts, keyboard(input, run));
          return;
        }
        input.onfocus = () => { this.typing = true; this.draw(); };
      }
    }
    const list = this.tab === "favorites" ? this.starred() : this.results;
    if (list === null) parts.push(hint(t.loading));
    else if (this.error) parts.push(hint(say(this.error)));
    else if (!list.length && this.tab === "favorites") parts.push(hint(t.noFavorites));
    else if (!list.length && this.tab === "search" && this.query) parts.push(hint(t.noResults));
    else for (const s of list) {
      parts.push(stationRow({
        title: s.name, info: s.info,
        active: state.source === "webradio" && state.detail.id === s.id,
        onPlay: () => api("/api/webradio/play", s),
        logo: s.logo,
        starred: isStarred({ kind: "webradio", station: s }),
        onStar: () => toggleStar({ kind: "webradio", title: s.name, station: s }),
      }));
    }
    const top = view.scrollTop;
    view.replaceChildren(...parts);
    view.scrollTop = top;
  },
  onState() {
    // a redraw would throw away what is being typed
    if (this.typing || (document.activeElement && document.activeElement.tagName === "INPUT")) return;
    this.draw();
  },
};

/* ---------- DAB+ ---------- */

const dab = {
  title: t.dab,
  services: [],
  slides: [],
  async render() {
    ({ services: this.services, slides: this.slides } = await api("/api/dab/services"));
    this.draw();
  },
  draw() {
    const scan = state.source === "dab" && state.detail.scan;
    const signal = state.source === "dab" && state.detail.signal;
    const parts = [h("div", { className: "toolbar" },
      h("button", { textContent: t.scan, disabled: !!scan, onclick: () => api("/api/dab/scan", {}) }),
      // reception of the playing station: bars, and the signal-to-noise ratio for aligning the antenna
      signal ? h("div", { className: `signal l${signal.level}` },
        h("span", { textContent: signal.level ? `${t.reception} ${signal.snr} dB` : t.noSignal }),
        h("i"), h("i"), h("i"), h("i")) : null)];
    // the picture the playing station sends along (cover, logo, programme info)
    if (state.source === "dab" && state.detail.slide) {
      if (!this.slides.includes(state.detail.sid)) this.slides.push(state.detail.sid);
      parts.push(h("img", { className: "slide", alt: "", src: `/api/dab/slide/${state.detail.sid}?v=${state.detail.slide}` }));
    }
    if (scan) parts.push(hint(`${t.scanning} ${scan.channel} · ${scan.found} ${t.found}`));
    else if (!this.services.length) parts.push(hint(t.noServices));
    else for (const s of this.services) {
      parts.push(stationRow({
        title: s.name, info: `${s.ensemble} · ${s.channel}`,
        logo: this.slides.includes(s.sid) ? `/api/dab/slide/${s.sid}` : null,
        active: state.source === "dab" && state.detail.sid === s.sid,
        onPlay: () => api("/api/dab/play", { sid: s.sid }),
        starred: isStarred({ kind: "dab", sid: s.sid }),
        onStar: () => toggleStar({ kind: "dab", title: s.name, sid: s.sid }),
      }));
    }
    const top = view.scrollTop;
    view.replaceChildren(...parts);
    view.scrollTop = top;
  },
  wasScanning: false,
  onState() {
    const scanning = !!(state.source === "dab" && state.detail.scan);
    if (this.wasScanning && !scanning) this.render(); else this.draw();
    this.wasScanning = scanning;
  },
};

/* ---------- FM ---------- */

const fm = {
  title: t.fm,
  mhz: 98.5,
  stations: [],
  names: {},
  sound: "auto",
  meter: h("p", { className: "label meter" }),
  fall: null,
  onSpectrum(s) {
    this.fall.push(s);
    this.meter.textContent = meterText(s);
  },
  async render() {
    this.fall = this.fall || makeWaterfall(hz => this.tune(Math.round(hz / 1e5) / 10));
    [this.stations, this.names, { fm_stereo: this.sound }] = await Promise.all(
      [api("/api/fm/stations"), api("/api/fm/names"), api("/api/settings")]);
    if (state.source === "fm" && state.detail.mhz) this.mhz = state.detail.mhz;
    this.draw();
  },
  tune(mhz) {
    this.mhz = Math.round(Math.min(108, Math.max(87.5, mhz)) * 100) / 100;
    this.draw();
    // several quick taps should retune the stick once, not once per tap
    clearTimeout(this.timer);
    // with the waterfall on, the receiver watches a wide band; without, only the station
    this.timer = setTimeout(() => api("/api/fm/tune", { mhz: this.mhz, waterfall: waterfallOn("fm") }), 400);
  },
  draw() {
    const scanning = state.source === "fm" && state.detail.scan;
    const step = (label, delta) => h("button", { textContent: label, onclick: () => this.tune(this.mhz + delta) });
    const chips = (label, list) => list.length ? [
      h("p", { className: "label", textContent: label }),
      h("div", { className: "chips" }, ...list.map(mhz => h("button", {
        className: mhz === this.mhz ? "on" : "", onclick: () => this.tune(mhz),
        textContent: this.names[mhz.toFixed(1)] ? `${this.names[mhz.toFixed(1)]} · ${mhz.toFixed(1)}` : mhz.toFixed(1),
      }))),
    ] : [];
    const name = this.names[this.mhz.toFixed(1)];
    const entry = { kind: "fm", mhz: this.mhz, title: (name ? `${name} · ` : "") + `${this.mhz.toFixed(2)} MHz` };
    const saved = isStarred(entry);
    view.replaceChildren(
      h("div", { className: "dial", innerHTML: `${this.mhz.toFixed(2)} <small>MHz</small>` }),
      ...(state.backends.fm === "engine" ? [this.meter, waterfallOn("fm") ? this.fall.el : null] : []).filter(Boolean),
      h("div", { className: "steps" }, step("− 1", -1), step("− 0.1", -0.1), step("+ 0.1", 0.1), step("+ 1", 1)),
      h("div", { className: "toolbar wrap" },
        h("button", { className: "primary", textContent: "▶", onclick: () => this.tune(this.mhz) }),
        h("button", {
          textContent: saved ? t.remove : t.save,
          onclick: () => toggleStar(entry),
        }),
        h("button", { textContent: t.scan, disabled: !!scanning, onclick: () => api("/api/fm/scan", {}) }),
        waterfallButton("fm", () => (state.source === "fm" ? this.tune(this.mhz) : this.draw())),
        state.backends.fm !== "engine" ? null : h("button", {
          textContent: `${t.sound}: ${t.soundModes[this.sound]}`,
          onclick: () => {
            const modes = Object.keys(t.soundModes);
            this.sound = modes[(modes.indexOf(this.sound) + 1) % modes.length];
            this.draw();
            api("/api/fm/stereo", { mode: this.sound });
          },
        }),
      ),
      ...(scanning ? [hint(t.fmScanning)] : []),
      ...chips(t.fmSaved, favorites.filter(f => f.kind === "fm").map(f => f.mhz).sort((a, b) => a - b)),
      ...chips(t.fmFound, this.stations.map(s => s.mhz)),
    );
  },
  wasScanning: false,
  onState() {
    const scanning = !!(state.source === "fm" && state.detail.scan);
    if (this.wasScanning && !scanning) this.render(); else if (scanning !== this.wasScanning) this.draw();
    this.wasScanning = scanning;
  },
};

/* ---------- receiver (free tuning) ---------- */

const MODE_NAMES = { nfm: "FM", wfm: "WFM", am: "AM", usb: "USB", lsb: "LSB" };
const SQUELCH_LEVELS = [0, 3, 6, 10, 15];   // dB above the noise floor
const ZOOMS = [1, 4, 16, 64];
const formatHz = hz => hz < 30e6
  ? `${(hz / 1e3).toFixed(1)} <small>kHz</small>` : `${(hz / 1e6).toFixed(4)} <small>MHz</small>`;

const tuner = {
  title: t.tuner,
  bands: [],
  get favorites() {
    return favorites.filter(f => f.kind === "tuner").map(f => ({ hz: f.hz, mode: f.mode, name: f.title }));
  },
  band: null,      // null shows the band list
  entry: null,     // digits typed on the number pad, null when it is closed
  hz: 145500000, mode: "nfm", squelch: 0, zoom: 1, label: "",
  meter: h("p", { className: "label meter" }),
  fall: null,
  onSpectrum(s) {
    this.fall.push(s);
    this.meter.textContent = meterText(s);
  },
  async render() {
    this.fall = this.fall || makeWaterfall(hz => {
      const step = this.band ? this.band.step : 1000;
      this.tune(Math.round(hz / step) * step);
    });
    this.bands = await api("/api/tuner/bands");
    this.draw();
  },
  back() {
    if (this.entry !== null) this.entry = null;
    else if (this.band) this.band = null;
    else return false;
    this.draw();
    return true;
  },
  open(band, preset) {
    this.band = band;
    this.squelch = band.squelch || 0;
    this.select(preset || band.presets[0]);
  },
  select(preset) {
    this.tune(preset.hz, preset.mode || this.band.mode, preset.name ? tr(preset.name) : "");
  },
  onair: [],
  // every channel between the band's lowest and highest preset, or just the presets if that is too many
  channels() {
    const all = this.band.presets.map(p => p.hz), step = this.band.step;
    const low = Math.min(...all), high = Math.max(...all), count = Math.round((high - low) / step) + 1;
    return count <= 240 ? Array.from({ length: count }, (_, i) => low + i * step) : all;
  },
  scan() {
    const scanning = state.source === "tuner" && state.detail.scan;
    if (scanning) return this.tune(this.hz, this.mode, this.label);   // tuning by hand ends the scan
    clearTimeout(this.timer);
    api("/api/tuner/scan", { channels: this.channels(), mode: this.mode, squelch: this.squelch || 6,
      waterfall: waterfallOn("tuner") }).catch(e => { this.error = e.message; this.draw(); });
  },
  async loadOnAir() {
    // the schedule only covers long, medium and shortwave
    this.onair = this.hz < 30e6 && this.mode !== "nfm" ? await api(`/api/tuner/onair?hz=${this.hz}`).catch(() => []) : [];
    if (current === this && this.band) this.draw();
  },
  tune(hz, mode = this.mode, label = "") {
    Object.assign(this, { hz: Math.round(Math.min(1.75e9, Math.max(1e5, hz))), mode, label, error: null });
    this.draw();
    clearTimeout(this.onairTimer);
    this.onairTimer = setTimeout(() => this.loadOnAir(), 900);
    clearTimeout(this.timer);
    this.timer = setTimeout(() => api("/api/tuner/tune",
      { hz: this.hz, mode: this.mode, squelch: this.mode === "nfm" ? this.squelch : 0, zoom: this.zoom, label: this.label,
        waterfall: waterfallOn("tuner") }), 400);
  },
  draw() {
    $("heading").textContent = this.band ? tr(this.band.name) : this.title;
    if (this.entry !== null) return this.drawPad();
    if (!this.band) return this.drawBands();
    const isFavorite = this.favorites.some(f => f.hz === this.hz && f.mode === this.mode);
    const step = (label, factor) => h("button", { textContent: label, onclick: () => this.tune(this.hz + factor * this.band.step) });
    const top = view.scrollTop;
    view.replaceChildren(
      h("div", { className: "dial", innerHTML: formatHz(this.hz), onclick: () => { this.entry = ""; this.draw(); } }),
      ...(state.backends.tuner === "engine" ? [this.meter, waterfallOn("tuner") ? this.fall.el : null] : []).filter(Boolean),
      h("div", { className: "steps five" }, ...Object.keys(MODE_NAMES).map(m => h("button", {
        className: m === this.mode ? "on" : "", textContent: MODE_NAMES[m], onclick: () => this.tune(this.hz, m, this.label),
      }))),
      h("div", { className: "steps" }, step("◀◀", -10), step("◀", -1), step("▶", 1), step("▶▶", 10)),
      h("div", { className: "toolbar wrap" },
        h("button", {
          className: "star" + (isFavorite ? " on" : ""), innerHTML: icon("star"),
          onclick: () => toggleStar({
            kind: "tuner", hz: this.hz, mode: this.mode, squelch: this.mode === "nfm" ? this.squelch : 0,
            title: this.label || formatHz(this.hz).replace(/<\/?small>/g, ""),
          }),
        }),
        this.mode === "nfm" ? h("button", {
          textContent: `${t.squelch}: ${this.squelch ? this.squelch + " dB" : t.off}`,
          onclick: () => {
            this.squelch = SQUELCH_LEVELS[(SQUELCH_LEVELS.indexOf(this.squelch) + 1) % SQUELCH_LEVELS.length];
            this.tune(this.hz, this.mode, this.label);
          },
        }) : null,
        state.backends.tuner !== "engine" || this.band.presets.length < 2 ? null : h("button", {
          className: state.source === "tuner" && state.detail.scan ? "on" : "",
          textContent: state.source === "tuner" && state.detail.scan ? t.stopScan : t.scanChannels,
          onclick: () => this.scan(),
        }),
        waterfallButton("tuner", () => this.tune(this.hz, this.mode, this.label)),
        state.backends.tuner !== "engine" || !waterfallOn("tuner") ? null : h("button", {
          textContent: `${t.zoom} ×${this.zoom}`,
          onclick: () => {
            this.zoom = ZOOMS[(ZOOMS.indexOf(this.zoom) + 1) % ZOOMS.length];
            this.tune(this.hz, this.mode, this.label);
          },
        }),
      ),
      ...(this.error ? [hint(say(this.error))] : []),
      ...(this.onair.length ? [h("p", { className: "label", textContent: t.onAir })] : []),
      ...this.onair.map(e => stationRow({
        title: e.station, info: `${e.khz} kHz · ${e.language}${e.target ? " → " + e.target : ""}`,
        active: e.khz * 1000 === this.hz, onPlay: () => this.tune(e.khz * 1000, "am", e.station),
      })),
      ...this.band.presets.map(p => stationRow({
        title: tr(p.name), info: `${formatHz(p.hz).replace(/<\/?small>/g, "")} · ${MODE_NAMES[p.mode || this.band.mode]}`,
        active: p.hz === this.hz, onPlay: () => this.select(p),
      })),
    );
    view.scrollTop = top;
  },
  onState() {
    // while the service scans, the display follows it
    if (this.band && state.source === "tuner" && state.detail.scan && state.detail.hz !== this.hz) {
      this.hz = state.detail.hz;
      this.label = "";
    }
    if (this.band && this.entry === null) this.draw();
  },
  drawBands() {
    const custom = { id: "custom", name: t.favorites, mode: "nfm", step: 12500, presets: this.favorites };
    view.replaceChildren(
      ...(this.favorites.length ? [stationRow({
        title: t.favorites, info: this.favorites.map(f => f.name || formatHz(f.hz).replace(/<\/?small>/g, "")).join(" · "),
        onPlay: () => this.open(custom),
      })] : []),
      ...this.bands.map(b => stationRow({
        title: tr(b.name), info: b.presets.slice(0, 4).map(p => tr(p.name)).join(" · "), onPlay: () => this.open(b),
      })),
    );
  },
  drawPad() {
    const key = (label, action) => h("button", { textContent: label, onclick: () => { action(); this.draw(); } });
    const digit = d => key(d, () => { if (this.entry.length < 9) this.entry += d; });
    const value = parseFloat(this.entry);
    view.replaceChildren(
      h("div", { className: "dial", textContent: this.entry || "–" }),
      h("p", { className: "label", textContent: t.enterFrequency }),
      h("div", { className: "pad" },
        ..."123456789".split("").map(digit),
        key(".", () => { if (!this.entry.includes(".")) this.entry += "."; }),
        digit("0"),
        key("⌫", () => { this.entry = this.entry.slice(0, -1); }),
        key(t.cancel, () => { this.entry = null; }),
        h("button", {
          className: "primary wide", textContent: "OK", disabled: !(value > 0),
          onclick: () => { this.entry = null; this.tune((value >= 2000 ? 1e3 : 1e6) * value); },
        }),
      ),
    );
  },
};

/* ---------- aircraft map ---------- */

function distanceKm([lat1, lon1], [lat2, lon2]) {
  const rad = Math.PI / 180;
  const a = Math.sin((lat2 - lat1) * rad / 2) ** 2
    + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin((lon2 - lon1) * rad / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(a));
}

let leaflet = null;
function loadLeaflet() {
  leaflet = leaflet || new Promise((resolve, reject) => {
    document.head.append(h("link", { rel: "stylesheet", href: "vendor/leaflet/leaflet.css" }));
    document.head.append(h("script", { src: "vendor/leaflet/leaflet.js", onload: resolve, onerror: reject }));
  });
  return leaflet;
}

const adsb = {
  title: t.adsb,
  map: null,
  markers: new Map(),
  centred: false,
  box: h("div", { className: "map" }),
  info: h("div", { className: "map-info" }),
  list: h("div", { className: "map-list", hidden: true }),
  async render() {
    const toggle = h("button", { className: "map-action", textContent: t.list, onclick: () => {
      this.list.hidden = !this.list.hidden;
      toggle.classList.toggle("on", !this.list.hidden);
    } });
    view.classList.add("flush");
    view.replaceChildren(this.box, this.info, this.list, toggle);
    await loadLeaflet();
    if (!this.map) {
      this.map = L.map(this.box).setView([51, 10], 6);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 14, attribution: "© OpenStreetMap",
      }).addTo(this.map);
    }
    this.map.invalidateSize();
    if (state.source !== "adsb") await api("/api/adsb/start", {});
    this.poll();
  },
  leave() {
    view.classList.remove("flush");
    clearTimeout(this.timer);
  },
  async poll() {
    if (current !== this) return;
    try {
      this.update(await api("/api/adsb/aircraft"));
    } catch (e) { /* the next poll tries again */ }
    this.timer = setTimeout(() => this.poll(), 2000);
  },
  update({ aircraft, location }) {
    const located = aircraft.filter(a => a.lat !== undefined && a.lon !== undefined);
    this.info.textContent = `${aircraft.length} ${t.aircraftSeen} · ${located.length} ${t.withPosition}`;
    if (!this.centred && (location || located.length)) {
      if (location) this.map.setView(location, 8);
      else this.map.fitBounds(located.map(a => [a.lat, a.lon]), { maxZoom: 9, padding: [40, 40] });
      this.centred = true;
    }
    const seen = new Set();
    for (const a of located) {
      seen.add(a.hex);
      const label = [a.flight || a.hex, a.altitude !== undefined ? `${Math.round(a.altitude / 100) * 100} ft` : null]
        .filter(Boolean).join(" · ");
      const icon = L.divIcon({
        className: "plane", iconSize: [28, 28],
        html: `<svg viewBox="0 0 24 24" style="transform: rotate(${a.track || 0}deg)">${ICONS.adsb}</svg><span></span>`,
      });
      let marker = this.markers.get(a.hex);
      if (!marker) this.markers.set(a.hex, marker = L.marker([a.lat, a.lon], { icon }).addTo(this.map));
      marker.setLatLng([a.lat, a.lon]).setIcon(icon);
      marker.getElement().querySelector("span").textContent = label;
    }
    for (const [hex, marker] of this.markers) {
      if (!seen.has(hex)) { marker.remove(); this.markers.delete(hex); }
    }
    // nearest first when the own position is known, otherwise the most recently heard
    const km = a => location && a.lat !== undefined ? distanceKm(location, [a.lat, a.lon]) : Infinity;
    const sorted = [...aircraft].sort((a, b) => km(a) - km(b) || a.seen - b.seen);
    this.list.replaceChildren(...sorted.map(a => stationRow({
      title: a.flight || a.hex,
      info: [
        a.altitude !== undefined ? `${Math.round(a.altitude / 100) * 100} ft` : null,
        a.speed !== undefined ? `${Math.round(a.speed)} kt` : null,
        km(a) < Infinity ? `${Math.round(km(a))} km` : null,
      ].filter(Boolean).join(" · "),
      onPlay: () => { if (a.lat !== undefined) this.map.panTo([a.lat, a.lon]); },
    })));
  },
};

/* ---------- weather ---------- */

// Open-Meteo reports WMO weather codes; neighbouring codes share a description
const describe = code => t.wmo[[95, 85, 80, 71, 66, 61, 51, 45, 3, 2, 1, 0].find(c => code >= c)] || "";

const weather = {
  title: t.weather,
  async render() {
    view.replaceChildren(hint(t.loading));
    let data;
    try {
      data = await api("/api/weather");
    } catch (e) {
      view.replaceChildren(hint(e.message === "no location set" ? t.needLocation : say(e.message)));
      return;
    }
    const day = (d, i) => h("div", { className: "day" },
      h("b", { textContent: i ? new Date(d.date).toLocaleDateString(lang, { weekday: "long" }) : t.today }),
      h("span", { textContent: describe(d.code) }),
      h("span", { textContent: `${Math.round(d.min)}° / ${Math.round(d.max)}°` }),
      h("small", { textContent: d.rain === null ? "" : `${t.rain} ${d.rain} %` }));
    $("heading").textContent = data.place ? `${t.weather} · ${data.place}` : t.weather;
    view.replaceChildren(
      h("div", { className: "dial", innerHTML: `${Math.round(data.now.temperature)}° <small>${describe(data.now.code)}</small>` }),
      h("p", { className: "label meter", textContent: `${t.wind} ${Math.round(data.now.wind)} km/h` }),
      ...data.days.map(day));
  },
};

/* ---------- location picker ---------- */

const locationPicker = {
  title: t.location,
  map: null,
  box: h("div", { className: "map crosshair" }),
  async render() {
    const save = h("button", { className: "primary map-action", textContent: t.locationSave, onclick: async () => {
      const centre = this.map.getCenter();
      await api("/api/location", { lat: centre.lat, lon: centre.lng });
      show(settings);
    } });
    view.classList.add("flush");
    view.replaceChildren(this.box, h("div", { className: "map-info", textContent: t.locationHint }), save);
    await loadLeaflet();
    const { location } = await api("/api/location");
    if (!this.map) {
      this.map = L.map(this.box);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 14, attribution: "© OpenStreetMap" }).addTo(this.map);
    }
    this.map.setView(location || [51, 10], location ? 11 : 6);
    this.map.invalidateSize();
  },
  back() { show(settings); return true; },
  leave() { view.classList.remove("flush"); },
};

/* ---------- alarm clock ---------- */

const alarm = {
  title: t.alarm,
  data: { enabled: false, time: "07:00" },
  async render() {
    this.data = await api("/api/alarm");
    this.draw();
  },
  async change(minutes, enabled = this.data.enabled, station) {
    const [hh, mm] = this.data.time.split(":").map(Number);
    const total = (hh * 60 + mm + minutes + 1440) % 1440;
    const time = `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
    Object.assign(this.data, { time, enabled });
    this.draw();
    await api("/api/alarm", { enabled, time, station });
    if (station) this.render();
  },
  draw() {
    const step = (label, minutes) => h("button", { textContent: label, onclick: () => this.change(minutes) });
    view.replaceChildren(
      h("div", { className: "dial", textContent: this.data.time }),
      h("div", { className: "steps" }, step("− 1 h", -60), step("− 5 min", -5), step("+ 5 min", 5), step("+ 1 h", 60)),
      h("div", { className: "toolbar" }, h("button", {
        className: this.data.enabled ? "primary" : "", textContent: this.data.enabled ? t.alarmOn : t.alarmOff,
        onclick: () => this.change(0, !this.data.enabled),
      })),
      h("p", { className: "label", textContent: t.wakesWith }),
      ...(this.data.last || this.data.fixed ? [
        stationRow({
          title: t.wakeLast, info: this.data.last || "", active: !this.data.fixed,
          onPlay: () => this.change(0, this.data.enabled, "last"),
        }),
        // pins whatever was heard last; to pick another station, play it first
        stationRow({
          title: this.data.fixed ? `${t.wakeFixed}: ${this.data.fixed}` : `${t.wakeFix}: ${this.data.last}`,
          info: this.data.fixed && this.data.last && this.data.last !== this.data.fixed ? `→ ${t.wakeFix}: ${this.data.last}` : "",
          active: !!this.data.fixed, onPlay: () => this.change(0, this.data.enabled, "fix"),
        }),
      ] : [hint(t.wakesWithNothing)]));
  },
  back() { show(settings); return true; },
};

/* ---------- Bluetooth ---------- */

const bluetooth = {
  title: t.bluetooth,
  status: { devices: [], visible: 0, scanning: false },
  busy: null,
  async render() {
    this.draw();
    this.refresh();
  },
  async refresh() {
    clearTimeout(this.timer);
    if (current !== this) return;
    try { this.status = await api("/api/bluetooth"); } catch (e) { /* try again below */ }
    this.draw();
    this.timer = setTimeout(() => this.refresh(), 3000);
  },
  async act(action, body, busy) {
    this.busy = busy;
    this.error = null;
    this.draw();
    try { this.status = await api(`/api/bluetooth/${action}`, body); } catch (e) { this.error = e.message; }
    this.busy = null;
    this.draw();
  },
  draw() {
    if (current !== this) return;
    const s = this.status;
    const top = view.scrollTop;
    view.replaceChildren(
      h("div", { className: "toolbar wrap" },
        h("button", {
          className: s.visible ? "primary" : "",
          textContent: s.visible ? `${t.btVisibleFor} ${s.visible} ${t.seconds}` : t.btVisible,
          onclick: () => this.act("visible", { on: !s.visible }),
        }),
        h("button", {
          textContent: this.busy === "scan" ? t.btScanning : t.btScan, disabled: this.busy === "scan",
          onclick: () => this.act("scan", {}, "scan"),
        })),
      ...(s.visible ? [hint(t.btPhoneHint)] : []),
      ...(this.error ? [hint(say(this.error))] : []),
      ...s.devices.map(d => stationRow({
        title: d.name, active: d.connected,
        info: this.busy === d.mac ? t.loading : d.connected ? t.btConnected : d.paired ? t.btPaired : t.btNew,
        onPlay: () => this.act(d.connected ? "disconnect" : "connect", { mac: d.mac }, d.mac),
      })));
    view.scrollTop = top;
  },
  leave() { clearTimeout(this.timer); },
};

/* ---------- device ---------- */

const deviceView = {
  title: t.device,
  info: null,
  note: "",
  confirm: null,
  async render() {
    this.info = await api("/api/device");
    this.draw();
  },
  draw() {
    const d = this.info;
    // switching the computer off takes two taps
    const twice = (id, label, action) => h("button", {
      className: this.confirm === id ? "primary" : "", textContent: this.confirm === id ? t.sure : label,
      onclick: () => {
        if (this.confirm === id) action();
        this.confirm = this.confirm === id ? null : id;
        this.draw();
      },
    });
    const bright = delta => h("button", { textContent: delta > 0 ? "+" : "−", onclick: async () => {
      d.brightness = (await api("/api/device/brightness", { percent: d.brightness + delta })).brightness;
      this.draw();
    } });
    view.replaceChildren(
      ...(d.brightness === null ? [] : [
        h("p", { className: "label", textContent: `${t.brightness}: ${d.brightness} %` }),
        h("div", { className: "steps" }, bright(-25), bright(-5), bright(5), bright(25))]),
      h("div", { className: "toolbar wrap" },
        d.wifi ? h("button", { textContent: t.wifi, onclick: () => show(wifiView) }) : null,
        // off keeps streams and the remote control from stalling on adapters that sleep too deeply
        d.wifi_powersave == null ? null : h("button", {
          className: d.wifi_powersave ? "on" : "", textContent: `${t.wifiSaving}: ${d.wifi_powersave ? t.on : t.off}`,
          onclick: async e => {
            e.target.disabled = true;
            try { await api("/api/device/wifi_powersave", { on: !d.wifi_powersave }); this.note = ""; }
            catch (error) { this.note = say(error.message); }
            this.render();
          },
        }),
        ...d.receivers.map(r => h("button", {
          className: r.on ? "on" : "", textContent: `${r.name}: ${r.on ? t.on : t.off}`,
          onclick: async () => { await api("/api/device/receiver", { id: r.id, on: !r.on }); this.render(); },
        })),
        d.update ? h("button", { textContent: t.update, onclick: async e => {
          e.target.disabled = true;
          this.note = t.updating;
          this.draw();
          try {
            this.note = (await api("/api/device/update", {})).changed ? t.updated : t.upToDate;
          } catch (error) { this.note = say(error.message); }
          this.draw();
        } }) : null),
      ...(this.note ? [hint(this.note)] : []),
      ...(d.power ? [h("div", { className: "toolbar wrap" },
        twice("reboot", t.restart, () => api("/api/device/power", { action: "reboot" })),
        twice("poweroff", t.shutDown, () => api("/api/device/power", { action: "poweroff" })))] : []),
      h("p", { className: "label meter", textContent: `RadioKiosk ${d.version}` }));
  },
  back() { show(settings); return true; },
};

const wifiView = {
  title: t.wifi,
  networks: null,
  chosen: null,      // the network a password is being typed for
  password: "",
  note: "",
  async render() {
    this.chosen = null;
    this.draw();
    this.networks = await api("/api/wifi").catch(() => []);
    if (current === this) this.draw();
  },
  async connect(name, password) {
    this.note = t.connecting;
    this.chosen = null;
    this.draw();
    try {
      await api("/api/wifi", { name, password });
      this.note = "";
    } catch (e) { this.note = say(e.message); }
    this.render();
  },
  draw() {
    if (this.chosen) {
      const input = h("input", { type: "text", value: this.password, autocapitalize: "off", autocomplete: "off" });
      const go = () => this.connect(this.chosen, input.value);
      input.oninput = () => { this.password = input.value; };
      input.onkeydown = e => { if (e.key === "Enter") go(); };
      if (keyboardWanted()) input.inputMode = "none";
      view.replaceChildren(
        h("p", { className: "label", textContent: `${t.wifiPassword} ${this.chosen}` }),
        h("div", { className: "toolbar" }, input, h("button", { className: "primary", textContent: t.connect, onclick: go })),
        ...(keyboardWanted() ? [keyboard(input, go)] : []));
      return;
    }
    view.replaceChildren(
      ...(this.note ? [hint(this.note)] : []),
      ...(this.networks === null ? [hint(t.loading)] : this.networks.map(n => stationRow({
        title: n.name, info: `${n.signal} %${n.connected ? " · " + t.connected : ""}`, active: n.connected,
        onPlay: () => {
          if (n.connected) return;
          if (!n.secured) return this.connect(n.name, "");
          Object.assign(this, { chosen: n.name, password: "" });
          this.draw();
        },
      }))));
  },
  back() {
    if (this.chosen) { this.chosen = null; this.draw(); } else show(deviceView);
    return true;
  },
};

/* ---------- settings ---------- */

/* ---------- typing a text ---------- */

// One view for every text that has to be typed: a feed's address, a key. It brings the on-screen keyboard.
const textPrompt = {
  title: "",
  label: "", value: "", done: null, origin: null,
  ask(options) { Object.assign(this, { value: "" }, options); show(this); },
  render() {
    const input = h("input", { type: "text", value: this.value, placeholder: this.label, autocapitalize: "off", spellcheck: false });
    const note = h("p", { className: "label" });
    const finish = async () => {
      try { await this.done(input.value.trim()); } catch (e) { note.textContent = say(e.message); return; }
      show(this.origin);
    };
    input.onkeydown = e => { if (e.key === "Enter") finish(); };
    const own = keyboardWanted();
    if (own) input.inputMode = "none";
    view.replaceChildren(h("p", { className: "label", textContent: this.label }), note,
      h("div", { className: "toolbar" }, input, h("button", { className: "primary", textContent: "OK", onclick: finish })),
      ...(own ? [keyboard(input, finish)] : []));
    if (!own) input.focus();
  },
  back() { show(this.origin); return true; },
};

const clockTime = seconds => {
  const s = Math.max(0, Math.round(seconds)), hours = Math.floor(s / 3600);
  const rest = `${String(Math.floor(s % 3600 / 60)).padStart(hours ? 2 : 1, "0")}:${String(s % 60).padStart(2, "0")}`;
  return hours ? `${hours}:${rest}` : rest;
};
const dayOf = unix => unix ? new Date(unix * 1000).toLocaleDateString(lang, { day: "numeric", month: "short", year: "numeric" }) : "";
const timeOf = unix => unix ? new Date(unix * 1000).toLocaleString(lang, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "";

/* ---------- podcasts ---------- */

const podcasts = {
  title: t.podcasts,
  tab: "subscriptions",
  typing: false,
  subscribed: [],
  suggested: [],
  results: [],
  query: "",
  error: null,
  async render() {
    ({ subscribed: this.subscribed, suggested: this.suggested } = await api("/api/podcasts"));
    this.draw();
  },
  async load(query) {
    this.results = null;
    this.error = null;
    this.draw();
    try { this.results = await api("/api/podcasts/search?q=" + encodeURIComponent(query)); }
    catch (e) { this.results = []; this.error = e.message; }
    if (current === this) this.draw();
  },
  draw() {
    const tabButton = id => h("button", {
      className: this.tab === id ? "on" : "", textContent: t[id],
      onclick: () => { Object.assign(this, { tab: id, typing: id === "search" && !this.results.length }); this.draw(); },
    });
    const parts = [h("div", { className: "tabs" }, tabButton("subscriptions"), tabButton("search"))];
    if (this.tab === "search") {
      const input = h("input", { type: "search", value: this.query, placeholder: t.search, enterKeyHint: "search" });
      const run = () => { this.query = input.value.trim(); this.typing = false; if (this.query) this.load(this.query); else this.draw(); };
      input.oninput = () => { this.query = input.value; };
      input.onkeydown = e => { if (e.key === "Enter") run(); };
      parts.push(h("div", { className: "toolbar" }, input, h("button", { className: "primary", textContent: t.go, onclick: run })));
      if (keyboardWanted()) {
        if (this.typing) {
          input.inputMode = "none";
          view.replaceChildren(...parts, keyboard(input, run));
          return;
        }
        input.onfocus = () => { this.typing = true; this.draw(); };
      }
    }
    const list = this.tab === "subscriptions" ? this.subscribed : this.results;
    if (list === null) parts.push(hint(t.loading));
    else if (this.error) parts.push(hint(say(this.error)));
    else if (!list.length) parts.push(hint(this.tab === "subscriptions" ? t.noSubscriptions : this.query ? t.noResults : ""));
    else for (const p of list) {
      parts.push(stationRow({ title: p.title, info: p.author, logo: p.image, onPlay: () => episodes.open(p) }));
    }
    if (this.tab === "subscriptions" && this.suggested.length) {
      parts.push(h("p", { className: "label", textContent: t.suggestions }),
        ...this.suggested.map(p => stationRow({ title: p.title, info: p.author, onPlay: () => episodes.open(p) })));
    }
    const top = view.scrollTop;
    view.replaceChildren(...parts);
    view.scrollTop = top;
  },
};

// The episodes of one podcast, with the controls of the one that is playing.
const episodes = {
  title: t.podcasts,
  podcast: null,
  list: null,
  error: null,
  open(podcast) { Object.assign(this, { podcast, list: null, error: null, title: podcast.title }); show(this); },
  async render() {
    this.draw();
    try { this.list = (await api("/api/podcasts/episodes?feed=" + encodeURIComponent(this.podcast.feed))).episodes; }
    catch (e) { this.list = []; this.error = e.message; }
    if (current === this) this.draw();
  },
  draw() {
    const subscribed = podcasts.subscribed.some(p => p.feed === this.podcast.feed);
    const mine = state.source === "podcast" && this.list && this.list.some(e => e.id === state.detail.id);
    const seek = seconds => h("button", { textContent: `${seconds > 0 ? "+" : "−"}${Math.abs(seconds)} s`,
      onclick: () => api("/api/podcasts/seek", { seconds }) });
    const parts = [h("div", { className: "toolbar wrap" },
      h("button", { className: subscribed ? "on" : "", textContent: subscribed ? t.subscribedOn : t.subscribe, onclick: async () => {
        await api("/api/podcasts/subscribe", { podcast: this.podcast, on: !subscribed });
        ({ subscribed: podcasts.subscribed, suggested: podcasts.suggested } = await api("/api/podcasts"));
        this.draw();
      } }),
      ...(mine ? [seek(-30), seek(30), h("span", { className: "label", textContent:
        state.detail.position === undefined ? "" : `${clockTime(state.detail.position)} / ${clockTime(state.detail.length)}` })] : []))];
    if (this.list === null) parts.push(hint(t.loading));
    else if (this.error) parts.push(hint(say(this.error)));
    else if (!this.list.length) parts.push(hint(t.noEpisodes));
    else for (const e of this.list) {
      parts.push(stationRow({
        title: e.title,
        info: [dayOf(e.date), e.seconds ? clockTime(e.seconds) : null, e.heard ? `${t.heardTo} ${clockTime(e.heard)}` : null]
          .filter(Boolean).join(" · "),
        active: state.source === "podcast" && state.detail.id === e.id,
        onPlay: () => api("/api/podcasts/play", { id: e.id, title: e.title, audio: e.audio, podcast: this.podcast.title }),
      }));
    }
    const top = view.scrollTop;
    view.replaceChildren(...parts);
    view.scrollTop = top;
  },
  onState() { this.draw(); },
  back() { show(podcasts); return true; },
};

const podcastSettings = {
  title: t.podcastDirectory,
  async render() {
    const s = await api("/api/settings");
    const set = async (key, value) => { await api("/api/settings", { key, value }); };
    const secretField = (key, label) => h("button", {
      textContent: `${label}: ${s[key] ? t.isSet : t.notSet}`,
      onclick: () => textPrompt.ask({ title: label, label, value: s[key], origin: this, done: value => set(key, value) }),
    });
    view.replaceChildren(
      h("p", { className: "explain", textContent: t.directoryHint }),
      h("div", { className: "toolbar wrap" }, ...Object.keys(t.directories).map(id => h("button", {
        className: s.podcast_provider === id ? "on" : "", textContent: t.directories[id],
        onclick: async () => { await set("podcast_provider", id); this.render(); },
      }))),
      ...(s.podcast_provider === "podcastindex" ? [h("div", { className: "toolbar wrap" },
        secretField("podcast_key", t.apiKey), secretField("podcast_secret", t.apiSecret))] : []));
  },
  back() { show(settings); return true; },
};

/* ---------- news reader ---------- */

// Refreshes itself while it is open; like the gallery it is there to be looked at, so no idle screen.
const news = {
  title: t.news,
  articles: null,
  feeds: [],
  timer: null,
  async render() {
    this.draw();
    await this.load();
  },
  async load() {
    clearTimeout(this.timer);
    try { ({ articles: this.articles, feeds: this.feeds, suggested: this.suggested } = await api("/api/feeds")); }
    catch (e) { this.articles = this.articles || []; }
    if (current !== this) return;
    this.draw();
    this.timer = setTimeout(() => this.load(), 60e3);
  },
  leave() { clearTimeout(this.timer); },
  draw() {
    const parts = [h("div", { className: "toolbar" },
      h("button", { textContent: t.manageFeeds, onclick: () => { feedList.origin = news; show(feedList); } }))];
    if (this.articles === null) parts.push(hint(t.loading));
    else if (!this.feeds.length) {
      // nothing chosen yet: offer the suggestions right here, one tap adds one
      parts.push(hint(t.noFeeds), ...(this.suggested || []).map(f => stationRow({
        title: f.title, info: f.url,
        onPlay: async () => { try { await api("/api/feeds", { action: "add", url: f.url }); } catch (e) { /* stays offered */ } this.load(); },
      })));
    } else if (!this.articles.length) parts.push(hint(t.noArticles));
    else for (const a of this.articles) {
      parts.push(stationRow({ title: a.title, info: [a.source, timeOf(a.date)].filter(Boolean).join(" · "),
        onPlay: () => article.open(a) }));
    }
    const top = view.scrollTop;
    view.replaceChildren(...parts);
    view.scrollTop = top;
  },
};

const article = {
  title: t.news,
  item: null,
  open(item) { this.item = item; show(this); },
  render() {
    const a = this.item;
    view.replaceChildren(h("div", { className: "article" },
      h("small", { textContent: [a.source, timeOf(a.date)].filter(Boolean).join(" · ") }),
      h("h2", { textContent: a.title }), h("p", { textContent: a.summary }), h("small", { textContent: a.link })));
  },
  back() { show(news); return true; },
};

const feedList = {
  title: t.manageFeeds,
  async render() {
    const { feeds, suggested } = await api("/api/feeds");
    const note = h("p", { className: "label" });
    view.replaceChildren(
      h("div", { className: "toolbar" }, h("button", { className: "primary", textContent: t.addFeed, onclick: () => textPrompt.ask({
        title: t.addFeed, label: t.feedAddress, value: "https://", origin: this,
        done: url => api("/api/feeds", { action: "add", url }),
      }) })),
      ...feeds.map(f => h("div", { className: "row" },
        h("button", {}, h("span", { className: "texts" }, h("b", { textContent: f.title }), h("small", { textContent: f.url }))),
        h("button", { className: "icon", textContent: "×", ariaLabel: t.remove,
          onclick: async () => { await api("/api/feeds", { action: "remove", url: f.url }); this.render(); } }))),
      ...(suggested.length ? [h("p", { className: "label", textContent: t.suggestions }), note] : []),
      ...suggested.map(f => h("div", { className: "row" },
        h("button", {}, h("span", { className: "texts" }, h("b", { textContent: f.title }), h("small", { textContent: f.url }))),
        h("button", { className: "icon", textContent: "+", ariaLabel: t.addFeed, onclick: async e => {
          e.target.disabled = true;
          try { await api("/api/feeds", { action: "add", url: f.url }); this.render(); }
          catch (error) { note.textContent = say(error.message); e.target.disabled = false; }
        } }))));
  },
  back() { show(this.origin || news); return true; },
};

/* ---------- wireless sensors ---------- */

const sensors = {
  title: t.sensors,
  timer: null,
  async render() {
    view.replaceChildren(hint(t.sensorsWaiting));
    if (state.source !== "sensors") await api("/api/sensors/start", {});
    this.poll();
  },
  leave() { clearTimeout(this.timer); },
  async poll() {
    if (current !== this) return;
    try { this.draw((await api("/api/sensors")).sensors); } catch (e) { /* the next poll tries again */ }
    this.timer = setTimeout(() => this.poll(), 2000);
  },
  draw(list) {
    const w = t.sensorWords;
    const top = view.scrollTop;
    view.replaceChildren(...(list.length ? list.map(s => stationRow({
      title: [s.temperature_C !== undefined ? `${s.temperature_C.toFixed(1)} °C` : null,
        s.humidity !== undefined ? `${Math.round(s.humidity)} % ${w.humidity}` : null,
        s.pressure_hPa !== undefined ? `${Math.round(s.pressure_hPa)} hPa` : null,
        s.wind_avg_km_h !== undefined ? `${w.wind} ${Math.round(s.wind_avg_km_h)} km/h` : null,
        s.rain_mm !== undefined ? `${w.rain} ${s.rain_mm} mm` : null].filter(Boolean).join(" · ") || s.model,
      info: [s.model, s.channel != null ? `${w.channel} ${s.channel}` : null, s.id != null ? `ID ${s.id}` : null,
        s.battery_ok === 0 ? w.battery : null,
        lang === "de" ? `${w.ago} ${clockTime(s.seen)}` : `${clockTime(s.seen)} ${w.ago}`].filter(Boolean).join(" · "),
      onPlay: () => {},
    })) : [hint(t.sensorsWaiting)]));
    view.scrollTop = top;
  },
};

/* ---------- ships ---------- */

const ships = {
  title: t.ais,
  map: null,
  markers: new Map(),
  centred: false,
  box: h("div", { className: "map" }),
  info: h("div", { className: "map-info" }),
  list: h("div", { className: "map-list", hidden: true }),
  async render() {
    const toggle = h("button", { className: "map-action", textContent: t.list, onclick: () => {
      this.list.hidden = !this.list.hidden;
      toggle.classList.toggle("on", !this.list.hidden);
    } });
    view.classList.add("flush");
    view.replaceChildren(this.box, this.info, this.list, toggle);
    await loadLeaflet();
    if (!this.map) {
      this.map = L.map(this.box).setView([51, 10], 6);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 16, attribution: "© OpenStreetMap" }).addTo(this.map);
    }
    this.map.invalidateSize();
    if (state.source !== "ais") await api("/api/ais/start", {});
    this.poll();
  },
  leave() {
    view.classList.remove("flush");
    clearTimeout(this.timer);
  },
  async poll() {
    if (current !== this) return;
    try { this.update(await api("/api/ais/ships")); } catch (e) { /* the next poll tries again */ }
    this.timer = setTimeout(() => this.poll(), 3000);
  },
  update({ ships: list, location }) {
    const located = list.filter(s => s.lat !== undefined);
    this.info.textContent = `${list.length} ${t.shipsSeen} · ${located.length} ${t.withPosition}`;
    if (!this.centred && (location || located.length)) {
      if (location) this.map.setView(location, 10);
      else this.map.fitBounds(located.map(s => [s.lat, s.lon]), { maxZoom: 12, padding: [40, 40] });
      this.centred = true;
    }
    const seen = new Set();
    for (const s of located) {
      seen.add(s.mmsi);
      const icon = L.divIcon({
        className: "plane", iconSize: [28, 28],
        html: `<svg viewBox="0 0 24 24" style="transform: rotate(${s.track || 0}deg)"><path d="M12 2l5 8v10H7V10z"/></svg><span></span>`,
      });
      let marker = this.markers.get(s.mmsi);
      if (!marker) this.markers.set(s.mmsi, marker = L.marker([s.lat, s.lon], { icon }).addTo(this.map));
      marker.setLatLng([s.lat, s.lon]).setIcon(icon);
      marker.getElement().querySelector("span").textContent = s.name || s.mmsi;
    }
    for (const [mmsi, marker] of this.markers) {
      if (!seen.has(mmsi)) { marker.remove(); this.markers.delete(mmsi); }
    }
    const km = s => location && s.lat !== undefined ? distanceKm(location, [s.lat, s.lon]) : Infinity;
    this.list.replaceChildren(...[...list].sort((a, b) => km(a) - km(b) || a.seen - b.seen).map(s => stationRow({
      title: s.name || String(s.mmsi),
      info: [s.speed !== undefined ? `${s.speed.toFixed(1)} kn` : null, s.destination ? `→ ${s.destination}` : null,
        km(s) < Infinity ? `${km(s).toFixed(1)} km` : null].filter(Boolean).join(" · "),
      onPlay: () => { if (s.lat !== undefined) this.map.panTo([s.lat, s.lon]); },
    })));
  },
};

/* ---------- timer and stopwatch ---------- */

// The countdown runs in the service and rings whatever the screen shows. The stopwatch
// only counts on this display; it keeps running while other views are open.
const timerView = {
  title: t.timer,
  tab: "timer",
  minutes: 5,
  ticker: null,
  render() {
    clearInterval(this.ticker);
    this.ticker = setInterval(() => this.draw(), 100);
    this.draw();
  },
  leave() { clearInterval(this.ticker); },
  draw() {
    const tabButton = (id, label) => h("button", { className: this.tab === id ? "on" : "", textContent: label,
      onclick: () => { this.tab = id; this.shown = null; this.draw(); } });
    const tabs = h("div", { className: "tabs" }, tabButton("timer", t.timer), tabButton("stopwatch", t.stopwatch));
    const timer = state.timer || {};
    let big, buttons, key;
    if (this.tab === "stopwatch") {
      const started = Number(pref("stopwatch_started", "0")), before = Number(pref("stopwatch_elapsed", "0"));
      const elapsed = before + (started ? Date.now() - started : 0);
      big = `${clockTime(Math.floor(elapsed / 1000))}.${Math.floor(elapsed % 1000 / 100)}`;
      key = `stopwatch ${!!started}`;
      buttons = () => [
        h("button", { className: "primary", textContent: started ? t.stopIt : t.start, onclick: () => {
          const since = Number(pref("stopwatch_started", "0"));   // read at the tap, not when the button was drawn
          if (since) setPref("stopwatch_elapsed", Number(pref("stopwatch_elapsed", "0")) + Date.now() - since);
          setPref("stopwatch_started", since ? 0 : Date.now());
        } }),
        h("button", { textContent: t.reset, onclick: () => { setPref("stopwatch_elapsed", 0); setPref("stopwatch_started", 0); } })];
    } else if (timer.ringing) {
      big = t.timeUp;
      key = "ringing";
      buttons = () => [h("button", { className: "primary", textContent: t.stopIt, onclick: () => api("/api/timer", { seconds: 0 }) })];
    } else if (timer.until) {
      big = clockTime(timer.until - Date.now() / 1000);
      key = "running";
      buttons = () => [h("button", { textContent: t.cancel, onclick: () => api("/api/timer", { seconds: 0 }) })];
    } else {
      big = clockTime(this.minutes * 60);
      key = "set";
      const step = by => h("button", { textContent: `${by > 0 ? "+" : "−"}${Math.abs(by)}`,
        onclick: () => { this.minutes = Math.max(1, Math.min(600, this.minutes + by)); } });
      buttons = () => [step(-5), step(-1), step(1), step(5),
        h("button", { className: "primary", textContent: t.start, onclick: () => api("/api/timer", { seconds: this.minutes * 60 }) })];
    }
    // only the digits change ten times a second; rebuilt buttons would swallow taps
    if (this.shown !== key || !view.querySelector(".big")) {
      this.shown = key;
      const presets = key === "set" ? [h("div", { className: "toolbar wrap center" }, ...[1, 3, 5, 10, 15, 20, 30, 45, 60].map(m =>
        h("button", { textContent: `${m} ${t.minutes}`, onclick: () => api("/api/timer", { seconds: m * 60 }) })))] : [];
      view.replaceChildren(tabs, h("div", { className: "big" }), h("div", { className: "toolbar wrap center" }, ...buttons()), ...presets);
    }
    view.querySelector(".big").classList.toggle("words", key === "ringing");
    view.querySelector(".big").textContent = big;
  },
  onState() { this.draw(); },
};

/* ---------- which tiles the start screen shows ---------- */

// Every tile but the settings, which are the way back here.
const tilesView = {
  title: t.tiles,
  render() { this.draw(); },
  draw() {
    const c = state.caps, hidden = state.hidden_tiles || [];
    const all = [["webradio", t.webradio], ["dab", t.dab], ["fm", t.fm], ["tuner", t.tuner], ["adsb", t.adsb],
      ...c.apps.map(a => [a.id, a.name]), ...(c.bluetooth ? [["bluetooth", t.bluetooth]] : []),
      ["podcast", t.podcasts], ["news", t.news], ["sensors", t.sensors], ["ais", t.ais], ["weather", t.weather],
      ["gallery", t.gallery], ["timer", t.timer]];
    const top = view.scrollTop;
    view.replaceChildren(h("p", { className: "explain", textContent: t.tilesHint }),
      h("div", { className: "toolbar wrap" }, ...all.map(([id, name]) => h("button", {
        className: hidden.includes(id) ? "" : "on", textContent: `${name}: ${hidden.includes(id) ? t.hiddenTile : t.shown}`,
        onclick: () => api("/api/settings", { key: "hidden_tiles",
          value: hidden.includes(id) ? hidden.filter(x => x !== id) : [...hidden, id] }),
      }))));
    view.scrollTop = top;
  },
  onState() { this.draw(); },
  back() { show(settings); return true; },
};

/* ---------- gallery ---------- */

let galleryInfo = null;   // folder, timing and number of pictures, as the service reports them
async function loadGallery() {
  try { galleryInfo = await api("/api/gallery"); } catch (e) { galleryInfo = null; }
  return galleryInfo;
}

// One slide show for the gallery tile and the idle screen: two stacked pictures that fade
// into each other. A picture is shown only once it has loaded, so a slow folder never shows half of one.
function slideShow() {
  const el = h("div", { className: "slides" }, h("img", { alt: "" }), h("img", { alt: "" }));
  let front = 0, order = [], at = -1, timer = null, running = false;
  const later = seconds => { clearTimeout(timer); if (running) timer = setTimeout(() => go(1), seconds * 1000); };
  function go(step) {
    if (!galleryInfo || !galleryInfo.count) return;
    if (order.length !== galleryInfo.count) {
      order = Array.from({ length: galleryInfo.count }, (_, i) => i);
      if (galleryInfo.shuffle) {
        for (let i = order.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1));
          [order[i], order[j]] = [order[j], order[i]];
        }
      }
      at = -1;
    }
    at = (Math.max(at, 0) + (at < 0 ? 0 : step) + order.length) % order.length;
    const next = el.children[1 - front];
    next.onload = () => {
      // "smart" crops a picture to the screen only where that costs less than a seventh of it
      const shape = next.naturalWidth / next.naturalHeight, screen = el.clientWidth / el.clientHeight;
      const little = Math.min(shape, screen) / Math.max(shape, screen) > 0.85;
      next.style.objectFit = galleryInfo.fit === "fill" || (galleryInfo.fit === "smart" && little) ? "cover" : "contain";
      el.children[front].classList.remove("shown");
      next.classList.add("shown");
      front = 1 - front;
    };
    next.onerror = () => later(1);   // unreadable picture: on to the next one
    // the service scales to the screen, so it needs to know its size
    next.src = `/api/gallery/picture/${order[at]}?w=${Math.round(innerWidth * devicePixelRatio)}&h=${Math.round(innerHeight * devicePixelRatio)}`;
    later(galleryInfo.seconds);
  }
  return {
    el,
    start() { if (!running) { running = true; go(1); } },
    stop() { running = false; clearTimeout(timer); },
    next: () => go(1), previous: () => go(-1),
  };
}

// The tile: nothing but the pictures. Header and bar leave after a moment; a tap in the middle
// brings them back, a tap at the left or right edge turns the page. What is playing keeps playing.
const galleryView = {
  title: t.gallery,
  slides: null,
  hideTimer: null,
  async render() {
    await loadGallery();
    if (current !== this) return;
    if (!galleryInfo || !galleryInfo.count) {
      view.replaceChildren(
        hint(galleryInfo && galleryInfo.folder ? (galleryInfo.missing ? t.folderMissing : t.galleryEmpty) : t.galleryUnset),
        h("div", { className: "toolbar center" },
          h("button", { className: "primary", textContent: t.gallerySetup, onclick: () => show(gallerySettings) })));
      return;
    }
    this.slides = slideShow();
    this.slides.el.onclick = e => {
      const x = e.clientX / innerWidth;
      if (x < 1 / 3) this.slides.previous();
      else if (x > 2 / 3) this.slides.next();
      else if (document.body.classList.contains("immersive")) this.immerse(6000);
      else document.body.classList.add("immersive");
    };
    view.classList.add("flush");
    view.replaceChildren(this.slides.el);
    this.slides.start();
    this.immerse(4000);
  },
  immerse(after) {
    clearTimeout(this.hideTimer);
    document.body.classList.remove("immersive");
    this.hideTimer = setTimeout(() => document.body.classList.add("immersive"), after);
  },
  leave() {
    clearTimeout(this.hideTimer);
    document.body.classList.remove("immersive");
    view.classList.remove("flush");
    if (this.slides) this.slides.stop();
    this.slides = null;
  },
};

const SLIDE_SECONDS = [5, 10, 15, 30, 60, 300];
const gallerySettings = {
  title: t.gallery,
  async render() {
    const g = await loadGallery();
    if (!g) { view.replaceChildren(hint(t.galleryUnset)); return; }
    const set = async (key, value) => { await api("/api/gallery", { key, value }); this.render(); };
    const every = g.seconds < 60 ? `${g.seconds} s` : `${g.seconds / 60} min`;
    view.replaceChildren(
      h("p", { className: "explain", textContent: t.galleryIntro }),
      h("p", { className: "label", textContent: !g.folder ? t.demoPictures
        : g.missing ? `${g.folder} · ${t.folderMissing}` : `${g.folder} · ${g.count} ${t.pictures}` }),
      h("div", { className: "toolbar wrap" },
        h("button", { className: g.folder ? "" : "primary", textContent: t.chooseFolder, onclick: () => folderPicker.open(g.start) }),
        h("button", { textContent: `${t.slideTime}: ${every}`,
          onclick: () => set("seconds", SLIDE_SECONDS[(SLIDE_SECONDS.indexOf(g.seconds) + 1) % SLIDE_SECONDS.length]) }),
        h("button", { className: g.shuffle ? "on" : "", textContent: `${t.shuffle}: ${g.shuffle ? t.on : t.off}`,
          onclick: () => set("shuffle", !g.shuffle) }),
        h("button", { className: g.subfolders ? "on" : "", textContent: `${t.subfoldersToo}: ${g.subfolders ? t.on : t.off}`,
          onclick: () => set("subfolders", !g.subfolders) }),
        h("button", { textContent: `${t.galleryFit}: ${t.galleryFits[g.fit]}`, onclick: () => {
          const fits = Object.keys(t.galleryFits);
          set("fit", fits[(fits.indexOf(g.fit) + 1) % fits.length]);
        } })),
      h("p", { className: "explain", textContent: t.galleryNetwork }));
  },
  back() { show(settings); return true; },
};

// Typing a path on a touch screen is no fun: walk through the folders instead.
const folderPicker = {
  title: t.chooseFolder,
  path: null,
  open(path) { this.path = path; show(this); },
  async render() {
    let d;
    try { d = await api(`/api/gallery/folders?path=${encodeURIComponent(this.path)}`); }
    catch (e) { view.replaceChildren(hint(say(e.message))); return; }
    const go = path => { this.path = path; view.scrollTop = 0; this.render(); };
    view.replaceChildren(
      h("p", { className: "label", textContent: d.path }),
      h("div", { className: "toolbar wrap" },
        h("button", { className: "primary", textContent: `${t.takeFolder} · ${d.pictures} ${t.picturesHere}`,
          onclick: async () => { await api("/api/gallery", { key: "folder", value: d.path }); show(gallerySettings); } }),
        ...(galleryInfo ? galleryInfo.places : []).filter(place => place !== d.path)
          .map(place => h("button", { textContent: place, onclick: () => go(place) }))),
      ...(d.parent ? [stationRow({ title: "‥", info: d.parent, onPlay: () => go(d.parent) })] : []),
      ...d.folders.map(name => stationRow({ title: name, onPlay: () => go(`${d.path.replace(/\/$/, "")}/${name}`) })));
  },
  back() { show(gallerySettings); return true; },
};

// Explains the two programs that turn the stick's data into sound, and lets each tile pick one.
const receiverView = {
  title: t.receiverSetting,
  async render() {
    const info = await api("/api/settings");
    const used = [info.fm_backend_used, info.tuner_backend_used];
    const card = (id, name, sub, points) => h("div", { className: used.includes(id) ? "used" : "" },
      h("b", { textContent: name }), h("small", { textContent: sub }),
      h("ul", {}, ...points.map(p => h("li", { className: p[0] === "+" ? "plus" : "minus", textContent: p.slice(1) }))));
    const names = { auto: t.choiceAuto, engine: t.engineName, rtl_fm: t.rtlName };
    const choice = (key, label) => [
      h("p", { className: "label", textContent: `${label} – ${t.runsWith}: ${names[info[key + "_used"]]}` }),
      h("div", { className: "toolbar" }, ...Object.keys(names).map(value => h("button", {
        className: info[key] === value ? "on" : "", textContent: names[value],
        disabled: value !== "auto" && !info.backends[value],
        onclick: async () => { await api("/api/settings", { key, value }); this.render(); },
      })))];
    const percent = x => Math.round(x * 100);
    const top = view.scrollTop;
    view.replaceChildren(
      h("p", { className: "explain", textContent: t.receiverIntro }),
      h("div", { className: "compare" },
        card("engine", t.engineName, t.engineSub, t.enginePoints), card("rtl_fm", t.rtlName, t.rtlSub, t.rtlPoints)),
      ...(info.engine_load == null ? [h("p", { className: "explain", textContent: t.loadNone })] : [
        // how hard the own receiver works this processor, with the limit of "automatic" as a mark
        h("div", { className: "load" },
          h("i", { style: `width: ${Math.min(100, percent(info.engine_load))}%` }),
          h("u", { style: `left: ${percent(info.engine_load_limit)}%` })),
        h("p", { className: "explain", textContent:
          `${t.loadNow.replace("{n}", percent(info.engine_load))} ${t.loadRule.replace("{n}", percent(info.engine_load_limit))}` })]),
      ...choice("fm_backend", t.fm), ...choice("tuner_backend", t.tuner));
    view.scrollTop = top;
  },
  back() { show(settings); return true; },
};

const settings = {
  title: t.settings,
  async render() {
    const [sinks, { location: position, name: place }, receivers] = await Promise.all(
      [api("/api/audio"), api("/api/location"), api("/api/settings")]);
    const SLEEP = [0, 15, 30, 60, 90];
    const left = state.sleep_until ? Math.max(1, Math.round((state.sleep_until - Date.now() / 1000) / 60)) : 0;
    const section = (name, ...buttons) => [h("h2", { className: "section", textContent: name }),
      ...(buttons.length ? [h("div", { className: "toolbar wrap" }, ...buttons)] : [])];
    // a setting of this display that steps through its choices
    const cycle = (label, key, fallback, names, apply) => h("button", {
      textContent: `${label}: ${names[pref(key, fallback)]}`,
      onclick: () => {
        const choices = Object.keys(names);
        setPref(key, choices[(choices.indexOf(pref(key, fallback)) + 1) % choices.length]);
        if (apply) apply();
        this.render();
      },
    });
    const top = view.scrollTop;
    view.replaceChildren(
      ...section(t.sectionPlayback,
        h("button", {
          textContent: `${t.sleepTimer}: ${left ? left + " " + t.minutes : t.off}`,
          onclick: async () => {
            const current = SLEEP.findIndex(m => m >= left);
            await api("/api/sleep", { minutes: left ? SLEEP[(current + 1) % SLEEP.length] : SLEEP[1] });
            setTimeout(() => this.render(), 150);
          },
        }),
        h("button", { textContent: `${t.alarm}: ${state.alarm || t.off}`, onclick: () => show(alarm) })),
      h("p", { className: "label", textContent: t.output }),
      ...sinks.map(s => stationRow({
        title: s.label, info: t.kinds[s.kind], active: s.active,
        onPlay: async () => { await api("/api/audio", { name: s.name }); this.render(); },
      })),

      ...section(t.sectionDisplay,
        h("button", {
          textContent: `${t.language}: ${t.languages[lang]}`,
          onclick: () => { setPref("lang", lang === "en" ? "de" : "en"); location.hash = "settings"; location.reload(); },
        }),
        cycle(t.theme, "theme", "dark", t.themes, () => { document.documentElement.dataset.theme = pref("theme", "dark"); }),
        cycle(t.bar, "bar", "medium", t.barSizes, () => { document.body.dataset.bar = pref("bar", "medium"); }),
        cycle(t.keyboard, "keyboard", "auto", t.keyboardModes),
        h("button", { textContent: t.tiles, onclick: () => show(tilesView) })),

      ...section(t.idle,
        h("button", {
          textContent: `${t.idleAfter}: ${Number(pref("idle", "2")) ? pref("idle", "2") + " " + t.minutes : t.off}`,
          onclick: () => {
            setPref("idle", IDLE_CHOICES[(IDLE_CHOICES.indexOf(Number(pref("idle", "2"))) + 1) % IDLE_CHOICES.length]);
            this.render();
          },
        }),
        h("button", {
          textContent: `${t.idleContent}: ${t.idleContents[state.idle_content || "clock"]}`,
          onclick: async () => {
            const kinds = Object.keys(t.idleContents);
            await api("/api/settings", { key: "idle_content", value: kinds[(kinds.indexOf(state.idle_content || "clock") + 1) % kinds.length] });
            this.render();
          },
        })),

      ...section(t.sectionContent,
        h("button", { textContent: t.gallery, onclick: () => show(gallerySettings) }),
        h("button", { textContent: t.podcastDirectory, onclick: () => show(podcastSettings) }),
        h("button", { textContent: t.manageFeeds, onclick: () => { feedList.origin = settings; show(feedList); } }),
        h("button", {
          textContent: `${t.location}: ${position ? place || t.locationSet : t.locationUnset}`, onclick: () => show(locationPicker),
        })),

      ...section(t.sectionReception,
        h("button", { textContent: t.receiverSetting, onclick: () => show(receiverView) }),
        h("button", { textContent: t.relevel, onclick: e => { e.target.disabled = true; api("/api/gain/reset", {}); } })),
      h("p", { className: "label", textContent: t.relevelHint }),

      ...section(t.sectionDevice,
        h("button", { textContent: t.device, onclick: () => show(deviceView) }),
        h("button", {
          className: receivers.remote ? "primary" : "",
          textContent: `${t.remote}: ${receivers.remote ? t.remoteOn : t.off}`,
          onclick: async () => { await api("/api/settings", { key: "remote", value: !receivers.remote }); this.render(); },
        })),
      ...(receivers.remote ? [h("p", { className: "label" },
        t.remoteHint, h("br"), h("b", { textContent: receivers.addresses.join("  ·  ") }), h("br"), t.remoteWarning,
        ...(receivers.stream ? [h("br"), h("br"), t.liveStream, h("br"),
          h("b", { textContent: receivers.addresses[receivers.addresses.length - 1] + "/live.mp3" })] : []))] : []),
      h("p", { className: "label meter", textContent: `RadioKiosk ${receivers.version}` }),
    );
    view.scrollTop = top;
  },
};

/* ---------- idle screen ---------- */

const IDLE_CHOICES = [0, 1, 2, 5, 15];   // minutes without a touch; 0 switches it off
const idle = $("idle");
let lastTouch = Date.now();
let idleWeather = null, idleWeatherAt = 0;

function drawIdle() {
  const now = new Date();
  $("idle-time").textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  $("idle-date").textContent = now.toLocaleDateString(lang, { weekday: "long", day: "numeric", month: "long" });
  $("idle-extra").textContent = [
    idleWeather ? [idleWeather.place, `${Math.round(idleWeather.temperature)}°`, describe(idleWeather.code)].filter(Boolean).join(" ") : null,
    state.alarm ? `⏰ ${state.alarm}` : null,
  ].filter(Boolean).join("  ·  ");
  const playing = state.source && state.status !== "error";
  $("idle-title").textContent = playing ? state.title : "";
  $("idle-text").textContent = playing ? say(state.text) : "";
  // shift a little every minute so nothing burns into the display
  const minute = now.getMinutes();
  $("idle-box").style.transform = `translate(${(minute % 5 - 2) * 14}px, ${(minute % 3 - 1) * 10}px)`;
  if (Date.now() - idleWeatherAt > 15 * 60e3) {
    idleWeatherAt = Date.now();
    api("/api/weather").then(w => { idleWeather = { ...w.now, place: w.place }; }, () => { idleWeather = null; });   // no location: no weather
  }
}

// The idle screen also dims the display where its brightness can be set; the first touch brings it back.
// The service keeps the brightness to return to. Requests go out one after another, so a touch
// right after the idle screen appeared cannot be overtaken by the dimming it cancels.
let dimmed = false, dimming = Promise.resolve();
function dim(on) {
  if (on === dimmed) return;
  dimmed = on;
  dimming = dimming.then(() => api("/api/device/dim", { on })).catch(() => { /* no adjustable backlight */ });
}

// With a gallery set up, its pictures run behind the clock and the display stays bright.
const idleSlides = slideShow();
idle.prepend(idleSlides.el);
let idleNewsAt = 0;
async function idleNews() {
  idleNewsAt = Date.now();
  try {
    // as many headlines as fit above the clock: three on a small screen
    const room = Math.max(1, Math.min(6, Math.floor((innerHeight - 180) / 90)));
    const newest = (await api("/api/feeds")).articles.slice(0, room);
    $("idle-news").replaceChildren(...newest.map(a => h("div", {},
      h("b", { textContent: a.title }), h("small", { textContent: [a.source, timeOf(a.date)].filter(Boolean).join(" · ") }))));
    return newest.length > 0;
  } catch (e) { return false; }
}
// Three kinds, a setting: the classic clock on black with the display dimmed, the gallery
// behind the clock, or the newest article. The last two keep the display bright.
async function showIdle() {
  idle.hidden = false;
  idle.classList.remove("pictures", "news");
  drawIdle();
  const content = state.idle_content;
  if (content === "gallery") {
    await loadGallery();
    if (idle.hidden) return;
    if (galleryInfo && galleryInfo.count) {
      idle.classList.add("pictures");
      idleSlides.start();
      return;
    }
  } else if (content === "feed") {
    const found = await idleNews();
    if (idle.hidden) return;
    if (found) {
      idle.classList.add("news");
      return;
    }
  }
  dim(true);
}
function hideIdle() {
  idle.hidden = true;
  idle.classList.remove("pictures", "news");
  idleSlides.stop();
}

// The first touch on the idle screen only wakes the display. The screen stays up until that
// tap is over; hidden at once, the tap would land on whatever tile lies beneath the finger.
let waking = false;
addEventListener("pointerdown", () => {
  lastTouch = Date.now();
  waking = !idle.hidden;
  if (waking) dim(false);
}, true);
for (const event of ["pointerup", "pointercancel"]) {
  addEventListener(event, () => { if (waking) setTimeout(() => { hideIdle(); waking = false; }, 350); }, true);
}
addEventListener("click", e => {   // the tap that woke the display ends here
  if (!waking) return;
  e.stopPropagation();
  hideIdle();
  waking = false;
}, true);
addEventListener("keydown", () => {
  lastTouch = Date.now();
  if (!idle.hidden) dim(false);
  hideIdle();
}, true);
setInterval(() => {
  const minutes = Number(pref("idle", "2"));
  // a map is there to be looked at, and so is the gallery
  const watching = [adsb, ships, locationPicker, news, article, sensors].includes(current)
    || (current === galleryView && galleryView.slides);
  if (idle.hidden && minutes && !watching && Date.now() - lastTouch > minutes * 60e3) showIdle();
  else if (!idle.hidden) {
    drawIdle();
    if (idle.classList.contains("news") && Date.now() - idleNewsAt > 60e3) idleNews();   // stays the newest article
  }
}, 1000);

/* ---------- shared chrome ---------- */

const tick = () => {
  const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const left = state.sleep_until ? Math.max(1, Math.round((state.sleep_until - Date.now() / 1000) / 60)) : 0;
  const timer = state.timer && state.timer.until ? `⏱ ${clockTime(state.timer.until - Date.now() / 1000)}` : null;
  $("clock").textContent = [timer, state.alarm ? `⏰ ${state.alarm}` : null, left ? `☾ ${left} ${t.minutes}` : null, time]
    .filter(Boolean).join(" · ");
};

function applyState(next) {
  const rang = state.timer && state.timer.ringing;
  state = next;
  if (state.timer && state.timer.ringing && !rang) {   // the timer is up: wake the display and say so
    dim(false);
    hideIdle();
    timerView.tab = "timer";
    if (current !== timerView) show(timerView);
  }
  const failed = state.status === "error";
  $("now").classList.toggle("error", failed);
  $("now-title").textContent = state.title || "";
  $("now-text").textContent = failed ? say(state.error) : state.status === "loading" ? t.loading : say(state.text) || "";
  $("vol").textContent = state.volume ?? "";
  $("stop").disabled = !state.source;
  $("rec").disabled = !state.recording && !(["webradio", "dab", "fm", "tuner", "podcast"].includes(state.source) && state.status === "playing");
  $("rec").classList.toggle("on", !!state.recording);
  if (state.recording && !failed) $("now-text").textContent = `● ${t.recordingTo}`;
  $("warn").hidden = !state.warnings.length;
  $("warn").textContent = state.warnings.map(w => t.warn[w] || w).join(" ");
  tick();
  if (current && current.onState) current.onState();
}

// deep links such as #fm or #tuner/2m open a view directly
async function openLink() {
  const [name, band] = location.hash.slice(1).split("/");
  if (name === "idle") showIdle();
  const target = { webradio, dab, fm, tuner, adsb, weather, bluetooth, alarm, settings, favorites: favoritesView, device: deviceView,
    wifi: wifiView, receiver: receiverView,
    gallery: galleryView, gallerysettings: gallerySettings, podcasts, news, sensors, ais: ships, timer: timerView,
    podcastsettings: podcastSettings, tiles: tilesView, feeds: feedList }[name] || home;
  if (target === webradio && band === "search") Object.assign(webradio, { tab: "search", typing: true });
  show(target);
  if (target === tuner && band) {
    const bands = await api("/api/tuner/bands");
    const match = bands.find(b => b.id === band);
    if (match) tuner.open(match);
  }
}

document.documentElement.dataset.theme = pref("theme", "dark");
document.body.dataset.bar = pref("bar", "medium");
let loadedVersion = null;
function connect() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.binaryType = "arraybuffer";
  ws.onmessage = e => {
    if (typeof e.data !== "string") {
      if (current && current.onSpectrum) current.onSpectrum(parseSpectrum(e.data));
      return;
    }
    const first = current === null;
    applyState({ warnings: [], ...JSON.parse(e.data) });
    if (first) api("/api/favorites").then(list => { favorites = list; openLink(); });
  };
  // after an update the service comes back with new files: load them
  ws.onopen = async () => {
    const { version, build } = await api("/api/settings");
    if (loadedVersion && build !== loadedVersion) location.reload();
    loadedVersion = build;
    $("version").textContent = `${t.version} ${version}`;
    $("version").hidden = current !== home;
  };
  ws.onclose = () => setTimeout(connect, 1500);
}

$("back").onclick = () => { if (!(current.back && current.back())) show(home); };
$("stop").onclick = () => api("/api/stop", {});
$("rec").onclick = () => api("/api/record", { on: !state.recording }).catch(() => {});
$("vol-down").onclick = () => api("/api/volume", { value: (state.volume ?? 50) - 5 });
$("vol-up").onclick = () => api("/api/volume", { value: (state.volume ?? 50) + 5 });

tick();
setInterval(tick, 10000);
connect();
