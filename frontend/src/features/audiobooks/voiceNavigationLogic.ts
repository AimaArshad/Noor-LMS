/**
 * Pure helpers for app-wide voice navigation ("open audiobooks", "go home",
 * "play physics 2nd year"). Kept free of React/network so they can be tested.
 */

export interface BookLike {
  id: string;
  title: string;
  classroom_name?: string;
  status: string;
}

const ORDINALS: Array<[RegExp, string]> = [
  [/\bfirst\b/g, "1st"],
  [/\bsecond\b/g, "2nd"],
  [/\bthird\b/g, "3rd"],
  [/\bfourth\b/g, "4th"],
];

/** Lower-case, strip punctuation, unify "audio book(s)" and spoken ordinals. */
export function normalise(s: string): string {
  let t = s.toLowerCase().replace(/[^a-z0-9\s]/g, " ");
  for (const [re, to] of ORDINALS) t = t.replace(re, to);
  t = t.replace(/\baudio\s*books\b/g, "audiobooks").replace(/\baudio\s*book\b/g, "audiobook");
  return t.replace(/\s+/g, " ").trim();
}

const STOP = new Set([
  "please", "the", "a", "an", "my", "audiobook", "audiobooks", "book", "books",
  "called", "named", "of", "for", "me", "to", "audio", "class",
]);

/** Words that mean "this is a transport / in-book command", not a book name. */
const TRANSPORT = new Set([
  "topic", "chapter", "page", "from", "next", "previous", "again", "it", "this",
  "that", "faster", "slower", "forward", "backward", "back", "section", "number",
]);

/** "play physics 2nd year" -> "physics 2nd year". Null when no book name is spoken. */
export function extractBookName(raw: string): string | null {
  const t = normalise(raw);
  const m = /^(?:please |can you |could you )?(?:play|open|start|read|listen to)\s+(.+)$/.exec(t);
  if (!m) return null;
  const words = m[1].split(" ");
  if (TRANSPORT.has(words[0])) return null;
  const name = words.filter((w) => !STOP.has(w)).join(" ");
  return name || null;
}

/** Best playable match for a spoken book name, or null (also null when ambiguous). */
export function findAudiobook<T extends BookLike>(name: string, books: T[]): T | null {
  const tokens = normalise(name)
    .split(" ")
    .filter((w) => w && !STOP.has(w));
  if (tokens.length === 0) return null;
  const playable = books.filter((b) => b.status === "ready" || b.status === "synthesizing");
  const hits = playable.filter((b) => {
    const hay = normalise(`${b.title} ${b.classroom_name ?? ""}`);
    return tokens.every((tok) => hay.includes(tok));
  });
  if (hits.length === 1) return hits[0];
  if (hits.length === 0) return null;
  const exact = hits.filter((b) => normalise(b.title) === tokens.join(" "));
  if (exact.length === 1) return exact[0];
  const shortest = Math.min(...hits.map((b) => normalise(b.title).length));
  const best = hits.filter((b) => normalise(b.title).length === shortest);
  return best.length === 1 ? best[0] : null;
}

export interface PageNav {
  kind: "home" | "classes" | "todo" | "library";
  path: string;
  speech: string;
}

/** "go home", "open my classes", "open audiobooks", "what audiobooks do I have". */
export function matchPageNavigation(raw: string): PageNav | null {
  const t = normalise(raw);
  const goVerb = /\b(open|go|show|take|navigate|list|display)\b/.test(t);

  if (/\bhome\b/.test(t) && /\b(go|take|back|open|navigate)\b/.test(t)) {
    return { kind: "home", path: "/", speech: "Going to the home page." };
  }
  if (goVerb && /\b(classes|classrooms|courses)\b/.test(t)) {
    return { kind: "classes", path: "/classes", speech: "Opening your classes." };
  }
  if (goVerb && /\b(to ?do|assignments)\b/.test(t)) {
    return { kind: "todo", path: "/todo", speech: "Opening your to do list." };
  }
  if (
    /\b(audiobook|audiobooks|library)\b/.test(t) &&
    (goVerb || /\b(what|which|read|my)\b/.test(t)) &&
    !/\b(play|chapter|topic|page|resume|start)\b/.test(t)
  ) {
    return { kind: "library", path: "/audiobooks", speech: "Audiobooks." };
  }
  return null;
}

/** What the library page reads aloud after "open audiobooks". */
export function describeLibrary(books: BookLike[]): string {
  const playable = books.filter((b) => b.status === "ready" || b.status === "synthesizing");
  if (playable.length === 0) return "You have no audiobooks yet.";
  const titles = playable.map((b) => b.title.replace(/[-_]/g, " ")).join(", ");
  const n = playable.length;
  return `You have ${n} audiobook${n === 1 ? "" : "s"}: ${titles}. Say play, followed by the book name.`;
}
