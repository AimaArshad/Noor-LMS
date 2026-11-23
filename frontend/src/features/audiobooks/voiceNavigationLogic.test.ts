import { describe, expect, it } from "vitest";

import {
  describeLibrary,
  extractBookName,
  findAudiobook,
  matchPageNavigation,
  normalise,
} from "./voiceNavigationLogic";

const books = [
  { id: "1", title: "physics-2nd year", classroom_name: "Physics", status: "ready" },
  { id: "2", title: "test audio", classroom_name: "Physics", status: "ready" },
  { id: "3", title: "chemistry 1st year", classroom_name: "Chemistry", status: "queued" },
];

describe("normalise", () => {
  it("unifies hyphens, ordinals and audio book", () => {
    expect(normalise("Physics-2nd Year")).toBe("physics 2nd year");
    expect(normalise("second year physics")).toBe("2nd year physics");
    expect(normalise("open my audio books")).toBe("open my audiobooks");
  });
});

describe("extractBookName", () => {
  it("returns the spoken book name", () => {
    expect(extractBookName("play physics 2nd year")).toBe("physics 2nd year");
    expect(extractBookName("Play the audiobook physics")).toBe("physics");
    expect(extractBookName("play second year physics")).toBe("2nd year physics");
  });
  it("ignores transport commands and bare page words", () => {
    expect(extractBookName("play topic kinetic theory")).toBeNull();
    expect(extractBookName("play chapter 2")).toBeNull();
    expect(extractBookName("play page 23")).toBeNull();
    expect(extractBookName("play")).toBeNull();
    expect(extractBookName("open audiobooks")).toBeNull();
    expect(extractBookName("open my audio books")).toBeNull();
  });
});

describe("findAudiobook", () => {
  it("matches title or classroom, case and hyphen insensitive", () => {
    expect(findAudiobook("physics 2nd year", books)?.id).toBe("1");
    expect(findAudiobook("test", books)?.id).toBe("2");
    expect(findAudiobook("2nd year physics", books)?.id).toBe("1");
  });
  it("skips books that cannot be played and unknown names", () => {
    expect(findAudiobook("chemistry", books)).toBeNull();
    expect(findAudiobook("biology", books)).toBeNull();
  });
  it("prefers the most specific title when several match", () => {
    const two = [...books, { id: "4", title: "physics", classroom_name: "Physics", status: "ready" }];
    expect(findAudiobook("physics", two)?.id).toBe("4");
  });
});

describe("matchPageNavigation", () => {
  it("home, classes, to-do", () => {
    expect(matchPageNavigation("go home")?.path).toBe("/");
    expect(matchPageNavigation("open my classes")?.path).toBe("/classes");
    expect(matchPageNavigation("show my to do list")?.path).toBe("/todo");
  });
  it("audiobook library", () => {
    expect(matchPageNavigation("open audiobooks")?.path).toBe("/audiobooks");
    expect(matchPageNavigation("list my audio books")?.path).toBe("/audiobooks");
    expect(matchPageNavigation("what audiobooks do I have")?.path).toBe("/audiobooks");
  });
  it("leaves everything else to the backend", () => {
    expect(matchPageNavigation("play physics")).toBeNull();
    expect(matchPageNavigation("go to chapter two")).toBeNull();
    expect(matchPageNavigation("faster")).toBeNull();
    expect(matchPageNavigation("help")).toBeNull();
  });
});

describe("describeLibrary", () => {
  it("reads only playable books", () => {
    expect(describeLibrary(books)).toBe(
      "You have 2 audiobooks: physics 2nd year, test audio. Say play, followed by the book name.",
    );
    expect(describeLibrary([])).toBe("You have no audiobooks yet.");
  });
});
